import json
import os
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')
users_table = dynamodb.Table('Users')

def lambda_handler(event, context):
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Auth-Email"
    }
    
    try:
        # Validate X-Auth-Email header (case-insensitive)
        auth_email = None
        if event.get('headers') and isinstance(event['headers'], dict):
            auth_email = event['headers'].get('X-Auth-Email', event['headers'].get('x-auth-email', '')).strip()
        if not auth_email:
            print("Missing X-Auth-Email header")
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "Missing X-Auth-Email header"})
            }

        # Fetch user details
        try:
            user_response = users_table.get_item(Key={'email': auth_email})
            user = user_response.get('Item')
            if not user:
                print("User not found for email:", auth_email)
                return {
                    "statusCode": 401,
                    "headers": headers,
                    "body": json.dumps({"error": "User not found"})
                }
            user_role = user.get('role', 'viewer')
            user_timelines = user.get('timelines', [])
        except ClientError as e:
            print(f"Error fetching user: {str(e)}")
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({"error": f"Failed to fetch user: {str(e)}"})
            }

        table_name = os.environ.get("EVENTS_TABLE")
        if not table_name:
            print("Error: EVENTS_TABLE environment variable not set")
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({"error": "Server configuration error: Missing EVENTS_TABLE"})
            }
        
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")
        table = dynamodb.Table(table_name)
        
        http_method = event.get("httpMethod", "")
        query_parameters = event.get("queryStringParameters", {}) or {}
        
        if http_method == "GET":
            timeline_name = query_parameters.get("timelineName")
            if not timeline_name:
                print("Missing timelineName for GET /events")
                return {
                    "statusCode": 400,
                    "headers": headers,
                    "body": json.dumps({"error": "Missing timelineName"})
                }

            # Role-based access control
            if user_role != 'super_admin' and timeline_name not in user_timelines:
                print(f"User {auth_email} not authorized for timeline {timeline_name}")
                return {
                    "statusCode": 403,
                    "headers": headers,
                    "body": json.dumps({"error": "Unauthorized: You do not have access to this timeline"})
                }

            try:
                response = table.query(
                    IndexName="TimelineNameIndex",
                    KeyConditionExpression="timelineName = :tn",
                    ExpressionAttributeValues={":tn": timeline_name}
                )
                events = response.get("Items", [])
                print(f"Fetched {len(events)} events for timeline: {timeline_name}")
                return {
                    "statusCode": 200,
                    "headers": headers,
                    "body": json.dumps({"events": events})
                }
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                error_message = e.response["Error"]["Message"]
                print(f"DynamoDB query error: {error_code} - {error_message}")
                return {
                    "statusCode": 500,
                    "headers": headers,
                    "body": json.dumps({"error": f"DynamoDB query error: {error_code} - {error_message}"})
                }
        
        if http_method == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": headers,
                "body": json.dumps({"message": "CORS preflight"})
            }
        
        print("Unsupported HTTP method:", http_method)
        return {
            "statusCode": 405,
            "headers": headers,
            "body": json.dumps({"error": "Method not allowed"})
        }
    
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        print(f"ClientError: {error_code} - {error_message}")
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": f"DynamoDB error: {error_code} - {error_message}"})
        }
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": f"Unexpected error: {str(e)}"})
        }