import json
import boto3
import bcrypt
from botocore.exceptions import ClientError
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')
users_table = dynamodb.Table('Users')

def lambda_handler(event, context):
    try:
        http_method = event['httpMethod']
        headers = event.get('headers', {})
        auth_email = headers.get('X-Auth-Email', '').strip()

        if not auth_email:
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Missing authentication email'}),
                'headers': {'Access-Control-Allow-Origin': '*'}
            }
        
        try:
            user_response = users_table.get_item(Key={'email': auth_email})
            if 'Item' not in user_response or user_response['Item']['role'] != 'super_admin':
                return {
                    'statusCode': 403,
                    'body': json.dumps({'error': 'Unauthorized: Super admin access required'}),
                    'headers': {'Access-Control-Allow-Origin': '*'}
                }
        except ClientError as e:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': f'Failed to verify user: {str(e)}'}),
                'headers': {'Access-Control-Allow-Origin': '*'}
            }

        if http_method == 'POST':
            return create_user(event)
        elif http_method == 'PUT':
            return update_user(event)
        elif http_method == 'DELETE':
            return delete_user(event)
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid HTTP method'}),
                'headers': {'Access-Control-Allow-Origin': '*'}
            }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Server error: {str(e)}'}),
            'headers': {'Access-Control-Allow-Origin': '*'}
        }

def create_user(event):
    try:
        body = json.loads(event['body'])
        email = body.get('email')
        password = body.get('password')
        role = body.get('role')
        timelines = body.get('timelines', [])

        if not email or not password or not role:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required fields: email, password, role'}),
                'headers': {'Access-Control-Allow-Origin': '*'}
            }
        if role not in ['super_admin', 'timeline_admin', 'viewer']:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid role'}),
                'headers': {'Access-Control-Allow-Origin': '*'}
            }

        existing_user = users_table.get_item(Key={'email': email}).get('Item')
        if existing_user:
            return {
                'statusCode': 409,
                'body': json.dumps({'error': 'User already exists'}),
                'headers': {'Access-Control-Allow-Origin': '*'}
            }

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=10)).decode('utf-8')
        now = datetime.utcnow().isoformat()

        users_table.put_item(Item={
            'email': email,
            'password': hashed_password,
            'role': role,
            'timelines': timelines,
            'createdAt': now,
            'updatedAt': now
        })

        return {
            'statusCode': 201,
            'body': json.dumps({'message': f'User {email} created successfully'}),
            'headers': {'Access-Control-Allow-Origin': '*'}
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Failed to create user: {str(e)}'}),
            'headers': {'Access-Control-Allow-Origin': '*'}
        }

def update_user(event):
    try:
        path_params = event.get('pathParameters', {})
        email = path_params.get('email')
        body = json.loads(event['body'])
        password = body.get('password')
        role = body.get('role')
        timelines = body.get('timelines')

        if not email:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing email in path'}),
                'headers': {'Access-Control-Allow-Origin': '*'}
            }

        existing_user = users_table.get_item(Key={'email': email}).get('Item')
        if not existing_user:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'User not found'}),
                'headers': {'Access-Control-Allow-Origin': '*'}
            }

        update_expression = 'SET updatedAt = :updatedAt'
        expression_values = {':updatedAt': datetime.utcnow().isoformat()}
        if password:
            update_expression += ', password = :password'
            expression_values[':password'] = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=10)).decode('utf-8')
        if role:
            if role not in ['super_admin', 'timeline_admin', 'viewer']:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid role'}),
                    'headers': {'Access-Control-Allow-Origin': '*'}
                }
            update_expression += ', role = :role'
            expression_values[':role'] = role
        if timelines is not None:
            update_expression += ', timelines = :timelines'
            expression_values[':timelines'] = timelines

        users_table.update_item(
            Key={'email': email},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values
        )

        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'User {email} updated successfully'}),
            'headers': {'Access-Control-Allow-Origin': '*'}
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Failed to update user: {str(e)}'}),
            'headers': {'Access-Control-Allow-Origin': '*'}
        }

def delete_user(event):
    try:
        path_params = event.get('pathParameters', {})
        email = path_params.get('email')

        if not email:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing email in path'}),
                'headers': {'Access-Control-Allow-Origin': '*'}
            }

        existing_user = users_table.get_item(Key={'email': email}).get('Item')
        if not existing_user:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'User not found'}),
                'headers': {'Access-Control-Allow-Origin': '*'}
            }

        users_table.delete_item(Key={'email': email})

        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'User {email} deleted successfully'}),
            'headers': {'Access-Control-Allow-Origin': '*'}
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Failed to delete user: {str(e)}'}),
            'headers': {'Access-Control-Allow-Origin': '*'}
        }