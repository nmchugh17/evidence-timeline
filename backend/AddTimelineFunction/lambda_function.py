import json
import boto3
import os
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')
users_table = dynamodb.Table('Users')
timelines_table = dynamodb.Table('Timelines')

def lambda_handler(event, context):
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Auth-Email'
    }
    print("Received event:", json.dumps(event))
    print("Headers received:", json.dumps(event.get('headers', {})))
    try:
        body = json.loads(event.get('body', '{}'))
        timeline_name = body.get('timelineName', '').strip()
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
        
        if not timeline_name:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing timelineName in request body'}),
                'headers': headers
            }
        
        # Verify user exists and has correct role
        try:
            response = users_table.get_item(Key={'email': auth_email})
            user = response.get('Item')
            if not user:
                return {
                    'statusCode': 401,
                    'body': json.dumps({'error': 'User not found'}),
                    'headers': headers
                }
            if user.get('role') not in ['timeline_admin', 'super_admin']:
                return {
                    'statusCode': 403,
                    'body': json.dumps({'error': 'Unauthorized: User does not have permission to add timelines'}),
                    'headers': headers
                }
        except Exception as e:
            print("Error fetching user:", str(e))
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to fetch user'}),
                'headers': headers
            }
        
        # Check if timeline already exists
        try:
            response = timelines_table.get_item(Key={'timelineName': timeline_name})
            if response.get('Item'):
                return {
                    'statusCode': 409,
                    'body': json.dumps({'error': 'Timeline already exists'}),
                    'headers': headers
                }
        except Exception as e:
            print("Error checking timeline:", str(e))
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to check timeline'}),
                'headers': headers
            }
        
        # Create new timeline
        try:
            current_time = datetime.utcnow().isoformat()
            timelines_table.put_item(
                Item={
                    'timelineName': timeline_name,
                    'createdAt': current_time,
                    'updatedAt': current_time
                }
            )
            
            # Update user's timelines if not super_admin
            if user.get('role') != 'super_admin':
                user_timelines = user.get('timelines', [])
                if timeline_name not in user_timelines:
                    user_timelines.append(timeline_name)
                    users_table.update_item(
                        Key={'email': auth_email},
                        UpdateExpression='SET timelines = :timelines',
                        ExpressionAttributeValues={':timelines': user_timelines}
                    )
            
            return {
                'statusCode': 201,
                'body': json.dumps({'message': f'Timeline {timeline_name} created successfully'}),
                'headers': headers
            }
        except Exception as e:
            print("Error creating timeline:", str(e))
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to create timeline'}),
                'headers': headers
            }
    
    except Exception as e:
        print("Unexpected error:", str(e))
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'}),
            'headers': headers
        }