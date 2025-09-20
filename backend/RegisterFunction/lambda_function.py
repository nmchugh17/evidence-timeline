import json
import boto3
import bcrypt
from botocore.exceptions import ClientError
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')
users_table = dynamodb.Table('Users')

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        email = body.get('email', '').strip()
        username = body.get('username', '').strip()
        password = body.get('password', '').strip()
        firstName = body.get('firstName', '').strip()
        surname = body.get('surname', '').strip()
        requestTimeline = body.get('requestTimeline', False)

        headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
        }

        if not email or not username or not password or not firstName or not surname:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required fields: email, username, password, firstName, surname'}),
                'headers': headers
            }

        # Check for existing email
        try:
            existing_email = users_table.get_item(Key={'email': email}).get('Item')
            if existing_email:
                return {
                    'statusCode': 409,
                    'body': json.dumps({'error': 'Email already exists'}),
                    'headers': headers
                }
        except ClientError as e:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'Failed to check email: {str(e)}'}),
                'headers': headers
            }

        # Check for existing username
        try:
            response = users_table.query(
                IndexName='UsernameIndex',
                KeyConditionExpression='username = :username',
                ExpressionAttributeValues={':username': username}
            )
            if response.get('Items'):
                return {
                    'statusCode': 409,
                    'body': json.dumps({'error': 'Username already exists'}),
                    'headers': headers
                }
        except ClientError as e:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'Failed to check username: {str(e)}'}),
                'headers': headers
            }

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=10)).decode('utf-8')
        now = datetime.utcnow().isoformat()

        users_table.put_item(Item={
            'email': email,
            'username': username,
            'password': hashed_password,
            'firstName': firstName,
            'surname': surname,
            'role': 'viewer',
            'timelines': [],
            'requestTimeline': requestTimeline,
            'createdAt': now,
            'updatedAt': now
        })

        return {
            'statusCode': 201,
            'body': json.dumps({'message': f'User {email} registered successfully'}),
            'headers': headers
        }

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON payload'}),
            'headers': headers
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Server error: {str(e)}'}),
            'headers': headers
        }