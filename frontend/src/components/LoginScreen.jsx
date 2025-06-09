import React, { useState } from 'react';
import useGameStore from '../state/gameStore';
import { apiService } from '../services/apiService';

function LoginScreen() {
    // Local state for the form inputs
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    // Get actions from our global store
    const loginAction = useGameStore((state) => state.login);

    const handleLogin = async (event) => {
        event.preventDefault();
        setIsLoading(true);
        setError('');

        try {
            const loginResponse = await apiService.loginUser(username, password);
            // Call the single action to update both token and session state
            console.log('[LoginScreen] Received from API:', loginResponse);
            loginAction(loginResponse.access_token);
        } catch (err) {
            // ... error handling is the same ...
            const errorDetail = err.data?.detail || err.message;
            setError(`Login failed: ${errorDetail}`);
            setIsLoading(false);
        }
    };
    return (
        <div className="login-container">
            <header className="header-text">
                <h1>Legend of the Solar Dragon's Tradewar</h1>
                <h2>(React Edition)</h2>
            </header>
            <form onSubmit={handleLogin} className="login-form">
                <h2>Login</h2>
                <div className="form-group">
                    <label htmlFor="username">Username</label>
                    <input
                        type="text"
                        id="username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        disabled={isLoading}
                        required
                    />
                </div>
                <div className="form-group">
                    <label htmlFor="password">Password</label>
                    <input
                        type="password"
                        id="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        disabled={isLoading}
                        required
                    />
                </div>
                {error && <p className="error-message">{error}</p>}
                <button type="submit" disabled={isLoading}>
                    {isLoading ? 'Logging in...' : 'Login'}
                </button>
            </form>
            {/* We can add a "Register" link/button here later */}
        </div>
    );
}

export default LoginScreen;