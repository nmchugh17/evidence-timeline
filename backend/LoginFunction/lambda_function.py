import json
import boto3
import bcrypt
import requests
from botocore.exceptions import ClientError
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')
users_table = dynamodb.Table('Users')
login_logs_table = dynamodb.Table('LoginLogs')

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        email = body.get('email', '').strip()
        password = body.get('password', '').strip()
        headers = event.get('headers', {})
        client_ip = headers.get('X-Forwarded-For', '').split(',')[0].strip() or 'unknown'

        response_headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
        }

        if not email or not password:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing email or password'}),
                'headers': response_headers
            }

        try:
            user_response = users_table.get_item(Key={'email': email}).get('Item')
            if not user_response:
                return {
                    'statusCode': 401,
                    'body': json.dumps({'error': 'Invalid email or password'}),
                    'headers': response_headers
                }

            stored_password = user_response['password'].encode('utf-8')
            if not bcrypt.checkpw(password.encode('utf-8'), stored_password):
                return {
                    'statusCode': 401,
                    'body': json.dumps({'error': 'Invalid email or password'}),
                    'headers': response_headers
                }

            # Fetch location from ip-api.com
            location = 'unknown'
            try:
                geo_response = requests.get(f'http://ip-api.com/json/{client_ip}', timeout=5)
                geo_data = geo_response.json()
                if geo_data.get('status') == 'success':
                    location = f"{geo_data['city']}, {geo_data['country']}"
                else:
                    print(f"Geolocation failed: {geo_data.get('message', 'Unknown error')}")
            except Exception as e:
                print(f"Geolocation error: {str(e)}")

            # Log to LoginLogs table
            try:
                login_logs_table.put_item(Item={
                    'username': user_response.get('username', email),
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'location': location
                })
                print(f"Logged login for user {user_response.get('username', email)} from {location}")
            except ClientError as e:
                print(f"Error logging to LoginLogs: {str(e)}")
                # Continue with login even if logging fails
                pass

            is_admin = user_response['role'] in ['super_admin', 'timeline_admin']
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'authenticated': True,
                    'isAdmin': is_admin,
                    'role': user_response['role'],
                    'timelines': user_response.get('timelines', []),
                    'email': email,
                    'username': user_response.get('username', '')
                }),
                'headers': response_headers
            }

        except ClientError as e:
            print(f"DynamoDB error: {str(e)}")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'Failed to authenticate: {str(e)}'}),
                'headers': response_headers
            }

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON payload'}),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'https://evidence-timeline-uploads.s3.eu-west-1.amazonaws.com',
                'Access-Control-Allow-Methods': 'POST,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
            }
        }
    except Exception as e:
        print(f"Server error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Server error: {str(e)}'}),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'https://evidence-timeline-uploads.s3.eu-west-1.amazonaws.com',
                'Access-Control-Allow-Methods': 'POST,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
            }
        }