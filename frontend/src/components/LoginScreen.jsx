import React, { useState } from 'react';
import useGameStore from '../state/gameStore';
import { apiService } from '../services/apiService';
import './LoginScreen.css';

function LoginScreen() {
    // New state to toggle between Login and Register modes
    const [isRegistering, setIsRegistering] = useState(false);
    
    // Local state for the form inputs
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState(''); // New field for registration
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState(''); // For successful registration
    const [isLoading, setIsLoading] = useState(false);

    // Get actions from our global store
    const loginAction = useGameStore((state) => state.login);

    const handleLogin = async () => {
        setIsLoading(true);
        setError('');
        setSuccessMessage('');
        try {
            const loginResponse = await apiService.loginUser(username, password);
            loginAction(loginResponse.access_token);
        } catch (err) {
            const errorDetail = err.data?.detail || err.message;
            setError(`Login failed: ${errorDetail}`);
            setIsLoading(false);
        }
    };

    const handleRegister = async () => {
        if (password !== confirmPassword) {
            setError('Passwords do not match.');
            return;
        }
        setIsLoading(true);
        setError('');
        setSuccessMessage('');
        try {
            await apiService.registerUser(username, password);
            setSuccessMessage('Registration successful! Please log in.');
            // Switch back to login view and clear fields
            setIsRegistering(false); 
            setUsername('');
            setPassword('');
            setConfirmPassword('');
        } catch (err) {
            const errorDetail = err.data?.detail || err.message;
            setError(`Registration failed: ${errorDetail}`);
        } finally {
            setIsLoading(false);
        }
    };
    
    const handleSubmit = (event) => {
        event.preventDefault();
        if (isRegistering) {
            handleRegister();
        } else {
            handleLogin();
        }
    };

    const toggleFormMode = () => {
        setIsRegistering(!isRegistering);
        setError('');
        setSuccessMessage('');
        setUsername('');
        setPassword('');
        setConfirmPassword('');
    };

    return (
        <div className="login-container">
            <header className="header-text">
                <h1>Legend of the Solar Dragon's Tradewar</h1>
                <h2>(React Edition)</h2>
            </header>
            <form onSubmit={handleSubmit} className="login-form">
                <h2>{isRegistering ? 'Register New Account' : 'Login'}</h2>
                
                {error && <p className="error-message">{error}</p>}
                {successMessage && <p className="success-message">{successMessage}</p>}
                
                <div className="form-group">
                    <label htmlFor="username">Username</label>
                    <input
                        type="text"
                        id="username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        disabled={isLoading}
                        required
                        autoComplete="username"
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
                        autoComplete={isRegistering ? "new-password" : "current-password"}
                    />
                </div>
                
                {isRegistering && (
                    <div className="form-group">
                        <label htmlFor="confirm-password">Confirm Password</label>
                        <input
                            type="password"
                            id="confirm-password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            disabled={isLoading}
                            required
                            autoComplete="new-password"
                        />
                    </div>
                )}
                
                <button type="submit" disabled={isLoading}>
                    {isLoading
                        ? (isRegistering ? 'Registering...' : 'Logging in...')
                        : (isRegistering ? 'Register' : 'Login')
                    }
                </button>

                <p className="form-toggle-link" onClick={toggleFormMode}>
                    {isRegistering
                        ? 'Already have an account? Login'
                        : "Don't have an account? Register"
                    }
                </p>
            </form>
        </div>
    );
}

export default LoginScreen;