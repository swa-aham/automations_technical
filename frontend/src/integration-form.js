import { useState } from 'react';
import {
    Box,
    Autocomplete,
    TextField,
    Typography,
    Paper,
} from '@mui/material';
import { AirtableIntegration } from './integrations/airtable';
import { NotionIntegration } from './integrations/notion';
import { HubspotIntegration } from './integrations/hubspot';
import { DataForm } from './data-form';

const integrationMapping = {
    'Notion': NotionIntegration,
    'Airtable': AirtableIntegration,
    'Hubspot': HubspotIntegration,
};

export const IntegrationForm = () => {
    const [integrationParams, setIntegrationParams] = useState({});
    const [user, setUser] = useState('TestUser');
    const [org, setOrg] = useState('TestOrg');
    const [currType, setCurrType] = useState(null);
    const CurrIntegration = integrationMapping[currType];

    return (
        <Box display='flex' justifyContent='center' alignItems='center' flexDirection='column' sx={{ width: '100%', p: 3 }}>
            <Paper elevation={3} sx={{ p: 3, width: '100%', maxWidth: '600px' }}>
                <Typography variant="h4" component="h1" gutterBottom align="center">
                    Integrations Portal
                </Typography>
                
                <Box display='flex' flexDirection='column'>
                    <TextField
                        label="User ID"
                        value={user}
                        onChange={(e) => setUser(e.target.value)}
                        sx={{mt: 2}}
                        fullWidth
                    />
                    <TextField
                        label="Organization ID"
                        value={org}
                        onChange={(e) => setOrg(e.target.value)}
                        sx={{mt: 2}}
                        fullWidth
                    />
                    <Autocomplete
                        id="integration-type"
                        options={Object.keys(integrationMapping)}
                        sx={{ width: '100%', mt: 2 }}
                        renderInput={(params) => <TextField {...params} label="Integration Type" />}
                        onChange={(e, value) => {
                            setCurrType(value);
                            setIntegrationParams({});
                        }}
                        value={currType}
                    />
                </Box>
                
                {currType && 
                <Box sx={{ mt: 4 }}>
                    <Typography variant="h6" gutterBottom>
                        {currType} Integration
                    </Typography>
                    <CurrIntegration 
                        user={user} 
                        org={org} 
                        integrationParams={integrationParams} 
                        setIntegrationParams={setIntegrationParams} 
                    />
                </Box>
                }
                
                {integrationParams?.credentials && 
                <Box sx={{mt: 4}}>
                    <Typography variant="h6" gutterBottom>
                        Data Fetching
                    </Typography>
                    <DataForm 
                        integrationType={integrationParams?.type} 
                        credentials={integrationParams?.credentials} 
                    />
                </Box>
                }
            </Paper>
        </Box>
    );
}