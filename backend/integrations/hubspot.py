# REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'
# authorization_url = f'https://app.hubspot.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=contacts%20oauth'

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

# Replace with your own credentials from HubSpot developer portal
CLIENT_ID = '16f6fe2d-c9d8-4bb4-b408-5023d670e49d'
CLIENT_SECRET = 'd5a328f5-2b7f-4d09-834b-76747308524e'
# CLIENT_ID = 'your-hubspot-client-id'
# CLIENT_SECRET = 'your-hubspot-client-secret'
encoded_client_id_secret = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()

REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'
authorization_url = f'https://app.hubspot.com/oauth/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=contacts%20content'

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
        raise HTTPException(status_code=400, detail=request.query_params.get('error_description', 'Authorization failed'))
    
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

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"HubSpot API error: {response.text}")

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

def create_integration_item_metadata_object(item, item_type):
    """Create an integration item metadata object from the response"""
    if item_type == "Contact":
        return IntegrationItem(
            id=str(item.get('id')),
            type=item_type,
            name=f"{item.get('properties', {}).get('firstname', '')} {item.get('properties', {}).get('lastname', '')}".strip() or f"Contact {item.get('id')}",
            creation_time=item.get('createdAt'),
            last_modified_time=item.get('updatedAt'),
        )
    elif item_type == "Company":
        return IntegrationItem(
            id=str(item.get('id')),
            type=item_type,
            name=item.get('properties', {}).get('name', f"Company {item.get('id')}"),
            creation_time=item.get('createdAt'),
            last_modified_time=item.get('updatedAt'),
        )
    elif item_type == "Deal":
        return IntegrationItem(
            id=str(item.get('id')),
            type=item_type,
            name=item.get('properties', {}).get('dealname', f"Deal {item.get('id')}"),
            creation_time=item.get('createdAt'),
            last_modified_time=item.get('updatedAt'),
        )
    else:  # For other types like Blog Posts, Forms, etc.
        return IntegrationItem(
            id=str(item.get('id')),
            type=item_type,
            name=item.get('properties', {}).get('name', f"{item_type} {item.get('id')}"),
            creation_time=item.get('createdAt') if 'createdAt' in item else None,
            last_modified_time=item.get('updatedAt') if 'updatedAt' in item else None,
        )

async def get_items_hubspot(credentials) -> list[IntegrationItem]:
    """Aggregates metadata relevant for a HubSpot integration"""
    credentials = json.loads(credentials)
    access_token = credentials.get("access_token")
    
    if not access_token:
        raise HTTPException(status_code=400, detail="Invalid HubSpot credentials")
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    
    # Initialize list to hold all integration items
    list_of_integration_item_metadata = []
    
    # Fetch contacts
    try:
        contacts_url = "https://api.hubapi.com/crm/v3/objects/contacts"
        response = requests.get(contacts_url, headers=headers, params={"limit": 100})
        if response.status_code == 200:
            contacts = response.json().get('results', [])
            for contact in contacts:
                list_of_integration_item_metadata.append(
                    create_integration_item_metadata_object(contact, "Contact")
                )
    except Exception as e:
        print(f"Error fetching contacts: {e}")
    
    # Fetch companies
    try:
        companies_url = "https://api.hubapi.com/crm/v3/objects/companies"
        response = requests.get(companies_url, headers=headers, params={"limit": 100})
        if response.status_code == 200:
            companies = response.json().get('results', [])
            for company in companies:
                list_of_integration_item_metadata.append(
                    create_integration_item_metadata_object(company, "Company")
                )
    except Exception as e:
        print(f"Error fetching companies: {e}")
    
    # Fetch deals
    try:
        deals_url = "https://api.hubapi.com/crm/v3/objects/deals"
        response = requests.get(deals_url, headers=headers, params={"limit": 100})
        if response.status_code == 200:
            deals = response.json().get('results', [])
            for deal in deals:
                list_of_integration_item_metadata.append(
                    create_integration_item_metadata_object(deal, "Deal")
                )
    except Exception as e:
        print(f"Error fetching deals: {e}")
    
    # Print the final list for debugging/verification
    print(f"list_of_integration_item_metadata: {list_of_integration_item_metadata}")
    
    return list_of_integration_item_metadata