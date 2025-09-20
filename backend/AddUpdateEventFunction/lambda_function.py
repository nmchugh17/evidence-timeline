import json
import os
import boto3
import base64
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')
users_table = dynamodb.Table('Users')

def lambda_handler(event, context):
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST,PUT,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Auth-Email"
    }
    
    try:
        print("Raw event:", json.dumps(event, default=str))
        http_method = event.get("httpMethod", "")
        path_parameters = event.get("pathParameters", {}) or {}
        event_id = path_parameters.get("eventId", None)
        
        # Validate X-Auth-Email header (case-insensitive)
        auth_email = None
        if event.get('headers') and isinstance(event['headers'], dict):
            auth_email = event['headers'].get('X-Auth-Email', event['headers'].get('x-auth-email', '')).strip()
        if not auth_email:
            print("Missing X-Auth-Email header")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing X-Auth-Email header"}),
                "headers": headers
            }

        # Fetch user details
        try:
            user_response = users_table.get_item(Key={'email': auth_email})
            user = user_response.get('Item')
            if not user:
                print("User not found for email:", auth_email)
                return {
                    "statusCode": 401,
                    "body": json.dumps({"error": "User not found"}),
                    "headers": headers
                }
            user_role = user.get('role', 'viewer')
            user_timelines = user.get('timelines', [])
        except ClientError as e:
            print(f"Error fetching user: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Failed to fetch user: {str(e)}"}),
                "headers": headers
            }

        # Handle Lambda Proxy payload
        if "body" in event:
            body_str = event.get("body", "{}")
            print("Raw body:", body_str)
            try:
                body = json.loads(body_str)
            except json.JSONDecodeError as e:
                print("JSON decode error:", str(e))
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Invalid JSON payload"}),
                    "headers": headers
                }
        else:
            body = event
            print("Direct payload:", body)
        
        print("Parsed body:", body)
        
        # Validate environment variables
        table_name = os.environ.get("EVENTS_TABLE")
        bucket_name = os.environ.get("MEDIA_BUCKET")
        if not table_name:
            print("Error: EVENTS_TABLE environment variable not set")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Server configuration error: Missing EVENTS_TABLE"}),
                "headers": headers
            }
        if not bucket_name:
            print("Error: MEDIA_BUCKET environment variable not set")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Server configuration error: Missing MEDIA_BUCKET"}),
                "headers": headers
            }
        
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")
        s3_client = boto3.client("s3", region_name="eu-west-1")
        table = dynamodb.Table(table_name)
        
        # Role-based access control for POST and PUT
        if http_method in ["POST", "PUT"]:
            timeline_name = body.get("timelineName", "").strip()
            if user_role == 'viewer':
                print(f"User {auth_email} is a viewer, cannot modify events")
                return {
                    "statusCode": 403,
                    "body": json.dumps({"error": "Unauthorized: Viewers cannot modify events"}),
                    "headers": headers
                }
            if user_role == 'timeline_admin' and timeline_name not in user_timelines:
                print(f"User {auth_email} not authorized for timeline {timeline_name}")
                return {
                    "statusCode": 403,
                    "body": json.dumps({"error": "Unauthorized: You do not have access to this timeline"}),
                    "headers": headers
                }

        if http_method == "POST":
            date = body.get("date", "")
            description = body.get("description", "")
            timeline_name = body.get("timelineName", "").strip()
            original_file_data = body.get("originalFile", "")
            cropped_file_data = body.get("croppedFile", "")
            
            if not date or not description or not timeline_name:
                print("Missing required fields")
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Missing required fields: date, description, timelineName"}),
                    "headers": headers
                }
            
            event_id = str(context.aws_request_id)
            event_data = {
                "eventId": event_id,
                "date": date,
                "description": description,
                "timelineName": timeline_name,
                "originalFileKey": "",
                "croppedFileKey": ""
            }
            
            # Handle file uploads to S3
            if original_file_data or cropped_file_data:
                try:
                    if not original_file_data and not cropped_file_data:
                        print("Empty file data received")
                        return {
                            "statusCode": 400,
                            "body": json.dumps({"error": "Empty file data"}),
                            "headers": headers
                        }
                    # Process original file
                    original_file_key = ""
                    if original_file_data:
                        if not original_file_data.startswith("data:") or ";base64," not in original_file_data:
                            print("Invalid original file_data format:", original_file_data[:100])
                            return {
                                "statusCode": 400,
                                "body": json.dumps({"error": "Invalid original file format: Expected base64-encoded data"}),
                                "headers": headers
                            }
                        mime_type, base64_data = original_file_data.split(",", 1)
                        print("Original MIME type:", mime_type)
                        if "/" not in mime_type or ";" not in mime_type:
                            print("Invalid original MIME type format:", mime_type)
                            return {
                                "statusCode": 400,
                                "body": json.dumps({"error": "Invalid original MIME type format"}),
                                "headers": headers
                            }
                        file_content = base64.b64decode(base64_data)
                        file_extension = mime_type.split("/")[1].split(";")[0]
                        if file_extension not in ["png", "jpeg", "jpg", "ogg", "mp3"]:
                            print("Unsupported original file extension:", file_extension)
                            return {
                                "statusCode": 400,
                                "body": json.dumps({"error": f"Unsupported original file type: {file_extension}"}),
                                "headers": headers
                            }
                        original_file_key = f"events/original/{event_id}.{file_extension}"
                        print(f"Uploading original file to S3: {original_file_key}, ContentType: {mime_type.split(';')[0]}")
                        s3_client.put_object(
                            Bucket=bucket_name,
                            Key=original_file_key,
                            Body=file_content,
                            ContentType=mime_type.split(";")[0]
                        )
                        event_data["originalFileKey"] = original_file_key
                        print(f"Uploaded original file to S3: {original_file_key}")
                    
                    # Process cropped file
                    cropped_file_key = ""
                    if cropped_file_data:
                        if not cropped_file_data.startswith("data:") or ";base64," not in cropped_file_data:
                            print("Invalid cropped file_data format:", cropped_file_data[:100])
                            return {
                                "statusCode": 400,
                                "body": json.dumps({"error": "Invalid cropped file format: Expected base64-encoded data"}),
                                "headers": headers
                            }
                        mime_type, base64_data = cropped_file_data.split(",", 1)
                        print("Cropped MIME type:", mime_type)
                        if "/" not in mime_type or ";" not in mime_type:
                            print("Invalid cropped MIME type format:", mime_type)
                            return {
                                "statusCode": 400,
                                "body": json.dumps({"error": "Invalid cropped MIME type format"}),
                                "headers": headers
                            }
                        file_content = base64.b64decode(base64_data)
                        file_extension = mime_type.split("/")[1].split(";")[0]
                        if file_extension not in ["png", "jpeg", "jpg"]:
                            print("Unsupported cropped file extension:", file_extension)
                            return {
                                "statusCode": 400,
                                "body": json.dumps({"error": f"Unsupported cropped file type: {file_extension}"}),
                                "headers": headers
                            }
                        cropped_file_key = f"events/cropped/{event_id}.{file_extension}"
                        print(f"Uploading cropped file to S3: {cropped_file_key}, ContentType: {mime_type.split(';')[0]}")
                        s3_client.put_object(
                            Bucket=bucket_name,
                            Key=cropped_file_key,
                            Body=file_content,
                            ContentType=mime_type.split(";")[0]
                        )
                        event_data["croppedFileKey"] = cropped_file_key
                        print(f"Uploaded cropped file to S3: {cropped_file_key}")
                except Exception as e:
                    print("S3 upload error:", str(e))
                    return {
                        "statusCode": 500,
                        "body": json.dumps({"error": f"S3 upload error: {str(e)}"}),
                        "headers": headers
                    }
            
            print("Saving event:", event_data)
            table.put_item(Item=event_data)
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Event added", "event": event_data}),
                "headers": headers
            }
        
        elif http_method == "PUT":
            if not event_id:
                print("Missing eventId")
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Missing eventId for update"}),
                    "headers": headers
                }
            date = body.get("date", "")
            description = body.get("description", "")
            timeline_name = body.get("timelineName", "").strip()
            original_file_data = body.get("originalFile", "")
            cropped_file_data = body.get("croppedFile", "")
            
            if not date or not description or not timeline_name:
                print("Missing required fields")
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Missing required fields: date, description, timelineName"}),
                    "headers": headers
                }
            
            # Fetch existing event
            print(f"Fetching existing event: {event_id}")
            response = table.get_item(Key={"eventId": event_id})
            item = response.get("Item")
            if not item or item.get("timelineName") != timeline_name:
                print("Event not found or timelineName mismatch:", event_id, timeline_name)
                return {
                    "statusCode": 404,
                    "body": json.dumps({"error": "Event not found or does not belong to specified timeline"}),
                    "headers": headers
                }
            old_original_file_key = item.get("originalFileKey", "")
            old_cropped_file_key = item.get("croppedFileKey", "")
            
            event_data = {
                "eventId": event_id,
                "date": date,
                "description": description,
                "timelineName": timeline_name,
                "originalFileKey": old_original_file_key,
                "croppedFileKey": old_cropped_file_key
            }
            
            # Clean up unreferenced S3 files
            try:
                # List all files with event_id prefix in original and cropped folders
                original_files = s3_client.list_objects_v2(
                    Bucket=bucket_name,
                    Prefix=f"events/original/{event_id}."
                ).get("Contents", [])
                cropped_files = s3_client.list_objects_v2(
                    Bucket=bucket_name,
                    Prefix=f"events/cropped/{event_id}."
                ).get("Contents", [])
                
                # Determine new file keys
                new_original_file_key = old_original_file_key
                new_cropped_file_key = old_cropped_file_key
                if original_file_data:
                    mime_type = original_file_data.split(",")[0]
                    file_extension = mime_type.split("/")[1].split(";")[0]
                    new_original_file_key = f"events/original/{event_id}.{file_extension}"
                if cropped_file_data:
                    mime_type = cropped_file_data.split(",")[0]
                    file_extension = mime_type.split("/")[1].split(";")[0]
                    new_cropped_file_key = f"events/cropped/{event_id}.{file_extension}"
                
                # Delete unreferenced original files
                for obj in original_files:
                    key = obj["Key"]
                    if key != new_original_file_key and key != old_original_file_key:
                        try:
                            s3_client.delete_object(Bucket=bucket_name, Key=key)
                            print(f"Deleted unreferenced original file: {key}")
                        except Exception as e:
                            print(f"Error deleting unreferenced original file {key} (ignored): {str(e)}")
                
                # Delete unreferenced cropped files
                for obj in cropped_files:
                    key = obj["Key"]
                    if key != new_cropped_file_key and key != old_cropped_file_key:
                        try:
                            s3_client.delete_object(Bucket=bucket_name, Key=key)
                            print(f"Deleted unreferenced cropped file: {key}")
                        except Exception as e:
                            print(f"Error deleting unreferenced cropped file {key} (ignored): {str(e)}")
            except Exception as e:
                print(f"Error listing or deleting unreferenced S3 files (ignored): {str(e)}")
            
            # Handle file uploads to S3
            if original_file_data or cropped_file_data:
                try:
                    if not original_file_data and not cropped_file_data:
                        print("Empty file data received")
                        return {
                            "statusCode": 400,
                            "body": json.dumps({"error": "Empty file data"}),
                            "headers": headers
                        }
                    # Process original file
                    if original_file_data:
                        if not original_file_data.startswith("data:") or ";base64," not in original_file_data:
                            print("Invalid original file_data format:", original_file_data[:100])
                            return {
                                "statusCode": 400,
                                "body": json.dumps({"error": "Invalid original file format: Expected base64-encoded data"}),
                                "headers": headers
                            }
                        mime_type, base64_data = original_file_data.split(",", 1)
                        print("Original MIME type:", mime_type)
                        if "/" not in mime_type or ";" not in mime_type:
                            print("Invalid original MIME type format:", mime_type)
                            return {
                                "statusCode": 400,
                                "body": json.dumps({"error": "Invalid original MIME type format"}),
                                "headers": headers
                            }
                        file_content = base64.b64decode(base64_data)
                        file_extension = mime_type.split("/")[1].split(";")[0]
                        if file_extension not in ["png", "jpeg", "jpg", "ogg", "mp3"]:
                            print("Unsupported original file extension:", file_extension)
                            return {
                                "statusCode": 400,
                                "body": json.dumps({"error": f"Unsupported original file type: {file_extension}"}),
                                "headers": headers
                            }
                        original_file_key = f"events/original/{event_id}.{file_extension}"
                        print(f"Uploading original file to S3: {original_file_key}, ContentType: {mime_type.split(';')[0]}")
                        s3_client.put_object(
                            Bucket=bucket_name,
                            Key=original_file_key,
                            Body=file_content,
                            ContentType=mime_type.split(";")[0]
                        )
                        event_data["originalFileKey"] = original_file_key
                        print(f"Uploaded original file to S3: {original_file_key}")
                    
                    # Process cropped file
                    if cropped_file_data:
                        if not cropped_file_data.startswith("data:") or ";base64," not in cropped_file_data:
                            print("Invalid cropped file_data format:", cropped_file_data[:100])
                            return {
                                "statusCode": 400,
                                "body": json.dumps({"error": "Invalid cropped file format: Expected base64-encoded data"}),
                                "headers": headers
                            }
                        mime_type, base64_data = cropped_file_data.split(",", 1)
                        print("Cropped MIME type:", mime_type)
                        if "/" not in mime_type or ";" not in mime_type:
                            print("Invalid cropped MIME type format:", mime_type)
                            return {
                                "statusCode": 400,
                                "body": json.dumps({"error": "Invalid cropped MIME type format"}),
                                "headers": headers
                            }
                        file_content = base64.b64decode(base64_data)
                        file_extension = mime_type.split("/")[1].split(";")[0]
                        if file_extension not in ["png", "jpeg", "jpg"]:
                            print("Unsupported cropped file extension:", file_extension)
                            return {
                                "statusCode": 400,
                                "body": json.dumps({"error": f"Unsupported cropped file type: {file_extension}"}),
                                "headers": headers
                            }
                        cropped_file_key = f"events/cropped/{event_id}.{file_extension}"
                        print(f"Uploading cropped file to S3: {cropped_file_key}, ContentType: {mime_type.split(';')[0]}")
                        s3_client.put_object(
                            Bucket=bucket_name,
                            Key=cropped_file_key,
                            Body=file_content,
                            ContentType=mime_type.split(";")[0]
                        )
                        event_data["croppedFileKey"] = cropped_file_key
                        print(f"Uploaded cropped file to S3: {cropped_file_key}")
                except Exception as e:
                    print("S3 upload error:", str(e))
                    return {
                        "statusCode": 500,
                        "body": json.dumps({"error": f"S3 upload error: {str(e)}"}),
                        "headers": headers
                    }
            
            print("Updating event:", event_data)
            try:
                table.put_item(Item=event_data)
                print(f"Successfully updated event in DynamoDB: {event_id}")
            except ClientError as e:
                print("DynamoDB put_item error:", str(e))
                return {
                    "statusCode": 500,
                    "body": json.dumps({"error": f"DynamoDB error: {str(e)}"}),
                    "headers": headers
                }
            
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Event updated", "event": event_data}),
                "headers": headers
            }
        
        elif http_method == "OPTIONS":
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "CORS preflight"}),
                "headers": headers
            }
        
        else:
            print("Unsupported HTTP method:", http_method)
            return {
                "statusCode": 405,
                "body": json.dumps({"error": "Method not allowed"}),
                "headers": headers
            }
    
    except ClientError as e:
        print("Client error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"DynamoDB or S3 error: {str(e)}"}),
            "headers": headers
        }
    except Exception as e:
        print("Unexpected error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Unexpected error: {str(e)}"}),
            "headers": headers
        }