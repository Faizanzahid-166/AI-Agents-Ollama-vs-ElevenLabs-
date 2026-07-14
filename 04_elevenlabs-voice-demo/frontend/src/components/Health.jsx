import React,{useEffect} from 'react'
import { HealthCheck } from '../services/api.js';


function Health() {
    useEffect(() => {
        const checkHealth = async () => {
            try {
                const healthData = await HealthCheck();
                console.log('Health check successful:', healthData);
            }
            catch (error) {
                console.error('Health check failed:', error);
            }
        };

        checkHealth();
    }, []);

    return (
        <div>
            <h2>Health Check</h2>
            <p>Check the console for health check results.</p>
        </div>
    )
}

export default Health
