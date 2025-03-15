import { useState } from 'react';
import {
    Box,
    TextField,
    Button,
    Typography,
    CircularProgress,
    Alert,
    Paper,
} from '@mui/material';
import axios from 'axios';

const endpointMapping = {
    'Notion': 'notion',
    'Airtable': 'airtable',
    'Hubspot': 'hubspot',
};

export const DataForm = ({ integrationType, credentials }) => {
    const [loadedData, setLoadedData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const endpoint = endpointMapping[integrationType];

    const handleLoad = async () => {
        setLoading(true);
        setError(null);
        
        try {
            const formData = new FormData();
            formData.append('credentials', JSON.stringify(credentials));
            
            let url;
            if (integrationType === 'Hubspot') {
                url = `http://localhost:8000/integrations/hubspot/get_hubspot_items`;
            } else {
                url = `http://localhost:8000/integrations/${endpoint}/load`;
            }
            
            const response = await axios.post(url, formData);
            const data = response.data;
            setLoadedData(data);
        } catch (e) {
            console.error("Error fetching data:", e);
            setError(e?.response?.data?.detail || "Error loading data");
        } finally {
            setLoading(false);
        }
    }

    const formatItemDisplay = (item, index) => {
        return (
            <Paper key={index} elevation={1} sx={{ p: 2, mb: 2 }}>
                <Typography variant="subtitle1" fontWeight="bold">{item.name || "Unnamed Item"}</Typography>
                <Typography variant="body2">ID: {item.id}</Typography>
                <Typography variant="body2">Type: {item.type}</Typography>
                {item.parent_id && (
                    <Typography variant="body2">Parent ID: {item.parent_id}</Typography>
                )}
                {item.creation_time && (
                    <Typography variant="body2">Created: {new Date(item.creation_time).toLocaleString()}</Typography>
                )}
                {item.last_modified_time && (
                    <Typography variant="body2">Modified: {new Date(item.last_modified_time).toLocaleString()}</Typography>
                )}
            </Paper>
        );
    }

    return (
        <Box display='flex' justifyContent='center' alignItems='center' flexDirection='column' width='100%'>
            <Box display='flex' flexDirection='row' gap={2} width='100%' mb={2}>
                <Button
                    onClick={handleLoad}
                    variant='contained'
                    fullWidth
                    disabled={loading}
                    startIcon={loading ? <CircularProgress size={20} /> : null}
                >
                    {loading ? 'Loading...' : 'Load Data'}
                </Button>
                <Button
                    onClick={() => {
                        setLoadedData(null);
                        setError(null);
                    }}
                    variant='outlined'
                    fullWidth
                    disabled={loading}
                >
                    Clear Data
                </Button>
            </Box>
            
            {error && (
                <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
                    {error}
                </Alert>
            )}
            
            {loadedData && (
                <Box sx={{ width: '100%', mt: 2 }}>
                    <Typography variant="h6" gutterBottom>
                        {Array.isArray(loadedData) ? `${loadedData.length} Items Found` : 'Data Loaded'}
                    </Typography>
                    
                    {Array.isArray(loadedData) ? (
                        <Box sx={{ maxHeight: '400px', overflow: 'auto' }}>
                            {loadedData.map((item, index) => formatItemDisplay(item, index))}
                        </Box>
                    ) : (
                        <TextField
                            value={JSON.stringify(loadedData, null, 2)}
                            multiline
                            fullWidth
                            rows={10}
                            InputProps={{ readOnly: true }}
                            variant="outlined"
                        />
                    )}
                </Box>
            )}
        </Box>
    );
}