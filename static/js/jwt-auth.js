/**
 * JWT Authentication Module for ApplyBaMa
 *
 * Handles token storage, automatic refresh, and API authentication
 * for the SPA dashboard and mobile/external applications.
 */

(function() {
    'use strict';

    const JWTAuth = {
        // Token storage keys
        ACCESS_TOKEN_KEY: 'applybama_access_token',
        REFRESH_TOKEN_KEY: 'applybama_refresh_token',
        USER_DATA_KEY: 'applybama_user_data',

        // Token refresh threshold (refresh 5 minutes before expiry)
        REFRESH_THRESHOLD_MINUTES: 5,

        // Refresh timer
        refreshTimer: null,

        /**
         * Initialize JWT authentication
         */
        init: function() {
            // Check if we have tokens on page load
            const accessToken = this.getAccessToken();
            if (accessToken) {
                this.scheduleTokenRefresh();
            }

            // Listen for storage events (multi-tab support)
            window.addEventListener('storage', (e) => {
                if (e.key === this.ACCESS_TOKEN_KEY || e.key === this.REFRESH_TOKEN_KEY) {
                    if (!e.newValue) {
                        // Tokens removed - redirect to login
                        this.handleTokenExpiry();
                    }
                }
            });
        },

        /**
         * Store JWT tokens in localStorage
         */
        storeTokens: function(access, refresh, userData = null) {
            try {
                localStorage.setItem(this.ACCESS_TOKEN_KEY, access);
                localStorage.setItem(this.REFRESH_TOKEN_KEY, refresh);

                if (userData) {
                    localStorage.setItem(this.USER_DATA_KEY, JSON.stringify(userData));
                }

                // Schedule automatic refresh
                this.scheduleTokenRefresh();

                // Dispatch custom event for other components
                window.dispatchEvent(new CustomEvent('jwt:tokens-stored', {
                    detail: { userData }
                }));

                return true;
            } catch (e) {
                console.error('Failed to store tokens:', e);
                return false;
            }
        },

        /**
         * Get access token from storage
         */
        getAccessToken: function() {
            return localStorage.getItem(this.ACCESS_TOKEN_KEY);
        },

        /**
         * Get refresh token from storage
         */
        getRefreshToken: function() {
            return localStorage.getItem(this.REFRESH_TOKEN_KEY);
        },

        /**
         * Get stored user data
         */
        getUserData: function() {
            const userData = localStorage.getItem(this.USER_DATA_KEY);
            return userData ? JSON.parse(userData) : null;
        },

        /**
         * Clear all tokens from storage
         */
        clearTokens: function() {
            localStorage.removeItem(this.ACCESS_TOKEN_KEY);
            localStorage.removeItem(this.REFRESH_TOKEN_KEY);
            localStorage.removeItem(this.USER_DATA_KEY);

            // Clear refresh timer
            if (this.refreshTimer) {
                clearTimeout(this.refreshTimer);
                this.refreshTimer = null;
            }

            // Dispatch custom event
            window.dispatchEvent(new CustomEvent('jwt:tokens-cleared'));
        },

        /**
         * Check if user is authenticated (has valid tokens)
         */
        isAuthenticated: function() {
            const accessToken = this.getAccessToken();
            const refreshToken = this.getRefreshToken();
            return !!(accessToken && refreshToken);
        },

        /**
         * Decode JWT token payload (without verification)
         */
        decodeToken: function(token) {
            try {
                const parts = token.split('.');
                if (parts.length !== 3) {
                    return null;
                }
                const payload = parts[1];
                const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
                return JSON.parse(decoded);
            } catch (e) {
                console.error('Failed to decode token:', e);
                return null;
            }
        },

        /**
         * Get token expiration time
         */
        getTokenExpiration: function(token) {
            const payload = this.decodeToken(token);
            if (!payload || !payload.exp) {
                return null;
            }
            // Convert Unix timestamp to Date
            return new Date(payload.exp * 1000);
        },

        /**
         * Check if token is expired or about to expire
         */
        isTokenExpiringSoon: function(token) {
            const expiration = this.getTokenExpiration(token);
            if (!expiration) {
                return true;
            }

            const now = new Date();
            const threshold = new Date(now.getTime() + (this.REFRESH_THRESHOLD_MINUTES * 60 * 1000));

            return expiration <= threshold;
        },

        /**
         * Schedule automatic token refresh before expiry
         */
        scheduleTokenRefresh: function() {
            // Clear existing timer
            if (this.refreshTimer) {
                clearTimeout(this.refreshTimer);
            }

            const accessToken = this.getAccessToken();
            if (!accessToken) {
                return;
            }

            const expiration = this.getTokenExpiration(accessToken);
            if (!expiration) {
                return;
            }

            const now = new Date();
            const timeUntilExpiry = expiration.getTime() - now.getTime();
            const refreshTime = timeUntilExpiry - (this.REFRESH_THRESHOLD_MINUTES * 60 * 1000);

            if (refreshTime <= 0) {
                // Token is already expiring soon, refresh immediately
                this.refreshAccessToken();
                return;
            }

            // Schedule refresh
            this.refreshTimer = setTimeout(() => {
                this.refreshAccessToken();
            }, refreshTime);
        },

        /**
         * Refresh access token using refresh token
         */
        refreshAccessToken: async function() {
            const refreshToken = this.getRefreshToken();

            if (!refreshToken) {
                this.handleTokenExpiry();
                return null;
            }

            try {
                const response = await fetch('/api/token/refresh/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ refresh: refreshToken })
                });

                if (!response.ok) {
                    throw new Error('Token refresh failed');
                }

                const data = await response.json();

                // Store new access token (keep existing refresh token)
                localStorage.setItem(this.ACCESS_TOKEN_KEY, data.access);

                if (data.user) {
                    localStorage.setItem(this.USER_DATA_KEY, JSON.stringify(data.user));
                }

                // Schedule next refresh
                this.scheduleTokenRefresh();

                // Dispatch refresh event
                window.dispatchEvent(new CustomEvent('jwt:token-refreshed', {
                    detail: { userData: data.user }
                }));

                return data.access;
            } catch (error) {
                console.error('Token refresh failed:', error);
                this.handleTokenExpiry();
                return null;
            }
        },

        /**
         * Handle token expiry (redirect to login)
         */
        handleTokenExpiry: function() {
            this.clearTokens();

            // Only redirect if we're not already on login page
            if (!window.location.pathname.includes('/auth/login/')) {
                window.dispatchEvent(new CustomEvent('jwt:token-expired'));

                // Optional: Redirect to login
                // window.location.href = '/auth/login/?next=' + encodeURIComponent(window.location.pathname);
            }
        },

        /**
         * Make authenticated API request with automatic token refresh
         */
        fetch: async function(url, options = {}) {
            let accessToken = this.getAccessToken();

            // Check if token needs refresh
            if (accessToken && this.isTokenExpiringSoon(accessToken)) {
                accessToken = await this.refreshAccessToken();
                if (!accessToken) {
                    throw new Error('Authentication required');
                }
            }

            // Add authorization header
            const headers = {
                ...options.headers,
                ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {})
            };

            try {
                const response = await fetch(url, {
                    ...options,
                    headers
                });

                // Handle 401 - try to refresh token and retry
                if (response.status === 401 && this.getRefreshToken()) {
                    const newToken = await this.refreshAccessToken();

                    if (newToken) {
                        // Retry with new token
                        const retryHeaders = {
                            ...options.headers,
                            'Authorization': `Bearer ${newToken}`
                        };

                        return fetch(url, {
                            ...options,
                            headers: retryHeaders
                        });
                    }
                }

                return response;
            } catch (error) {
                console.error('API request failed:', error);
                throw error;
            }
        },

        /**
         * Login with credentials and store tokens
         */
        login: async function(username, password) {
            try {
                const response = await fetch('/api/token/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, password })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Login failed');
                }

                const data = await response.json();
                this.storeTokens(data.access, data.refresh, data.user);

                return {
                    success: true,
                    user: data.user
                };
            } catch (error) {
                console.error('Login failed:', error);
                return {
                    success: false,
                    error: error.message
                };
            }
        },

        /**
         * Logout and clear tokens
         */
        logout: async function() {
            try {
                // Notify server (optional)
                await fetch('/api/logout/', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${this.getAccessToken()}`,
                        'Content-Type': 'application/json'
                    }
                });
            } catch (error) {
                console.error('Logout request failed:', error);
            } finally {
                // Always clear tokens locally
                this.clearTokens();
            }
        },

        /**
         * Verify token validity
         */
        verifyToken: async function(token) {
            try {
                const response = await fetch('/api/token/verify/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ token: token || this.getAccessToken() })
                });

                const data = await response.json();
                return data.valid;
            } catch (error) {
                console.error('Token verification failed:', error);
                return false;
            }
        }
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => JWTAuth.init());
    } else {
        JWTAuth.init();
    }

    // Export to global scope
    window.JWTAuth = JWTAuth;

})();
