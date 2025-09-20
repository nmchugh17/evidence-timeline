import json
import os
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')
s3_client = boto3.client('s3', region_name='eu-west-1')
users_table = dynamodb.Table('Users')
table = dynamodb.Table('TimelineEvents')

def lambda_handler(event, context):
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'DELETE,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Auth-Email'
    }

    try:
        # Validate X-Auth-Email header (case-insensitive)
        auth_email = None
        if event.get('headers') and isinstance(event['headers'], dict):
            auth_email = event['headers'].get('X-Auth-Email', event['headers'].get('x-auth-email', '')).strip()
        if not auth_email:
            print("Missing X-Auth-Email header")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing X-Auth-Email header'}),
                'headers': headers
            }

        # Fetch user details
        try:
            user_response = users_table.get_item(Key={'email': auth_email})
            user = user_response.get('Item')
            if not user:
                print("User not found for email:", auth_email)
                return {
                    'statusCode': 401,
                    'body': json.dumps({'error': 'User not found'}),
                    'headers': headers
                }
            user_role = user.get('role', 'viewer')
            user_timelines = user.get('timelines', [])
        except ClientError as e:
            print(f"Error fetching user: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'Failed to fetch user: {str(e)}'}),
                'headers': headers
            }

        path_params = event.get('pathParameters', {})
        query_params = event.get('queryStringParameters', {}) or {}
        event_id = path_params.get('eventId')
        timeline_name = query_params.get('timelineName')

        if not event_id or not timeline_name:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing eventId or timelineName'}),
                'headers': headers
            }

        # Role-based access control
        if user_role == 'viewer':
            print(f"User {auth_email} is a viewer, cannot delete events")
            return {
                'statusCode': 403,
                'body': json.dumps({'error': 'Unauthorized: Viewers cannot delete events'}),
                'headers': headers
            }
        if user_role == 'timeline_admin' and timeline_name not in user_timelines:
            print(f"User {auth_email} not authorized for timeline {timeline_name}")
            return {
                'statusCode': 403,
                'body': json.dumps({'error': 'Unauthorized: You do not have access to this timeline'}),
                'headers': headers
            }

        # Verify event exists and belongs to timeline
        response = table.get_item(Key={'eventId': event_id}).get('Item')
        if not response or response.get('timelineName') != timeline_name:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Event not found or does not belong to specified timeline'}),
                'headers': headers
            }

        # Get S3 bucket name from environment variable
        bucket_name = os.environ.get('MEDIA_BUCKET', 'evidence-timeline-media')
        if not bucket_name:
            print("Error: MEDIA_BUCKET environment variable not set")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Server configuration error: Missing MEDIA_BUCKET'}),
                'headers': headers
            }

        # Delete associated S3 files
        original_file_key = response.get('originalFileKey', '')
        cropped_file_key = response.get('croppedFileKey', '')
        deleted_files = []

        try:
            # Delete original file if it exists
            if original_file_key:
                print(f"Deleting S3 object: {original_file_key}")
                s3_client.delete_object(Bucket=bucket_name, Key=original_file_key)
                deleted_files.append(original_file_key)
                print(f"Successfully deleted S3 object: {original_file_key}")

            # Delete cropped file if it exists
            if cropped_file_key:
                print(f"Deleting S3 object: {cropped_file_key}")
                s3_client.delete_object(Bucket=bucket_name, Key=cropped_file_key)
                deleted_files.append(cropped_file_key)
                print(f"Successfully deleted S3 object: {cropped_file_key}")
        except ClientError as e:
            print(f"Error deleting S3 objects: {str(e)}")
            # Log error but proceed with DynamoDB deletion
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'Failed to delete S3 objects: {str(e)}. Proceeding with DynamoDB deletion.'}),
                'headers': headers
            }

        # Delete event from DynamoDB
        try:
            table.delete_item(Key={'eventId': event_id})
            print(f"Successfully deleted event from DynamoDB: {event_id}")
        except ClientError as e:
            print(f"Error deleting event from DynamoDB: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'Failed to delete event from DynamoDB: {str(e)}'}),
                'headers': headers
            }

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'message': 'Event deleted successfully',
                'deletedFiles': deleted_files
            }),
            'headers': headers
        }

    except ClientError as e:
        print(f"ClientError: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'DynamoDB or S3 error: {str(e)}'}),
            'headers': headers
        }
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Server error: {str(e)}'}),
            'headers': headers
        }