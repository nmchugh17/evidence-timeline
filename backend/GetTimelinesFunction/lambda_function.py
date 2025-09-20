import json
import boto3
import os

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')
users_table = dynamodb.Table('Users')
timelines_table = dynamodb.Table('Timelines')

def lambda_handler(event, context):
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Auth-Email'
    }
    print("Received event:", json.dumps(event))
    print("Headers received:", json.dumps(event.get('headers', {})))
    try:
        auth_email = None
        if event.get('headers') and isinstance(event['headers'], dict):
            # Check for both cases
            auth_email = event['headers'].get('X-Auth-Email', event['headers'].get('x-auth-email', '')).strip()
            print("X-Auth-Email:", auth_email)
        if not auth_email:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing X-Auth-Email header'}),
                'headers': headers
            }
        
        # Verify user exists in Users table
        try:
            response = users_table.get_item(Key={'email': auth_email})
            user = response.get('Item')
            if not user:
                return {
                    'statusCode': 401,
                    'body': json.dumps({'error': 'User not found'}),
                    'headers': headers
                }
        except Exception as e:
            print("Error fetching user:", str(e))
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to fetch user'}),
                'headers': headers
            }
        
        # Get timelines
        try:
            timelines_response = timelines_table.scan()
            all_timelines = [item['timelineName'] for item in timelines_response.get('Items', [])]
            user_role = user.get('role', 'viewer')
            user_timelines = user.get('timelines', [])
            
            if user_role == 'super_admin':
                allowed_timelines = all_timelines
            elif user_role == 'timeline_admin':
                allowed_timelines = user_timelines
            else:  # viewer
                allowed_timelines = user_timelines
            
            return {
                'statusCode': 200,
                'body': json.dumps({'timelines': allowed_timelines}),
                'headers': headers
            }
        except Exception as e:
            print("Error fetching timelines:", str(e))
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to fetch timelines'}),
                'headers': headers
            }
    
    except Exception as e:
        print("Unexpected error:", str(e))
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'}),
            'headers': headers
        }