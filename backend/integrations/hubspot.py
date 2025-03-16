# hubspot.py

import json
import secrets
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import base64
import requests
from integrations.integration_item import IntegrationItem

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

# You'll need to create these in the HubSpot developer portal
CLIENT_ID = '130beac9-4d93-4f1c-8b4f-23eb3f08afed'
CLIENT_SECRET = '911464f7-4728-4bb4-816c-4db745e68818'
encoded_client_id_secret = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()

REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'
authorization_url = f'https://app.hubspot.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=oauth'

async def authorize_hubspot(user_id, org_id):
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', json.dumps(state_data), expire=600)

    return f'{authorization_url}&state={encoded_state}'

async def oauth2callback_hubspot(request: Request):
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error_description', 'Unknown error'))
    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))

    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')

    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')

    async with httpx.AsyncClient() as client:
        response, _ = await asyncio.gather(
            client.post(
                'https://api.hubapi.com/oauth/v1/token',
                data={
                    'grant_type': 'authorization_code',
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                    'redirect_uri': REDIRECT_URI,
                    'code': code
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            ),
            delete_key_redis(f'hubspot_state:{org_id}:{user_id}'),
        )

    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(response.json()), expire=600)
    
    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)

async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')

    return credentials

def create_integration_item_metadata_object(
    item, item_type, parent_id=None, parent_name=None
) -> IntegrationItem:
    """Creates an integration item metadata object from HubSpot response"""
    integration_item = IntegrationItem(
        id=str(item.get('id', '')),
        name=item.get('properties', {}).get('name', item.get('name', '')),
        type=item_type,
        parent_id=parent_id,
        parent_path_or_name=parent_name,
        creation_time=item.get('createdAt', None),
        last_modified_time=item.get('updatedAt', None),
    )
    
    return integration_item

async def get_items_hubspot(credentials) -> list[IntegrationItem]:
    """Retrieves HubSpot items and returns them as IntegrationItem objects"""
    credentials = json.loads(credentials)
    access_token = credentials.get('access_token')
    
    if not access_token:
        raise HTTPException(status_code=400, detail="Access token not found")
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    
    # Get contacts
    contacts_response = requests.get('https://api.hubapi.com/crm/v3/objects/contacts', headers=headers)
    
    # Get companies
    companies_response = requests.get('https://api.hubapi.com/crm/v3/objects/companies', headers=headers)
    
    # Get deals
    deals_response = requests.get('https://api.hubapi.com/crm/v3/objects/deals', headers=headers)
    
    integration_items = []
    
    # Process contacts
    if contacts_response.status_code == 200:
        contacts_data = contacts_response.json()
        for contact in contacts_data.get('results', []):
            integration_items.append(create_integration_item_metadata_object(contact, 'Contact'))
    
    # Process companies
    if companies_response.status_code == 200:
        companies_data = companies_response.json()
        for company in companies_data.get('results', []):
            integration_items.append(create_integration_item_metadata_object(company, 'Company'))
    
    # Process deals
    if deals_response.status_code == 200:
        deals_data = deals_response.json()
        for deal in deals_data.get('results', []):
            integration_items.append(create_integration_item_metadata_object(deal, 'Deal'))
    
    print(f"HubSpot integration items: {integration_items}")
    return integration_items