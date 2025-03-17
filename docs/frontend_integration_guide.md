# Frontend Integration Guide for Sentient Inbox API

This guide provides practical instructions for integrating the Sentient Inbox Backend API with your frontend application. It builds upon the detailed [API Documentation](./api_documentation.md).

## Getting Started

To integrate with the Sentient Inbox Backend, your frontend application will need to:

1. Implement the authentication flow
2. Make authenticated API requests
3. Handle responses and errors properly
4. Manage user state and permissions

## Authentication Implementation

### Basic Setup

Set up a central authentication service in your frontend application:

```javascript
// src/services/auth.service.js
export class AuthService {
  constructor() {
    this.baseUrl = 'http://localhost:8000'; // or your production API URL
    this.tokenKey = 'sentient_inbox_token';
    this.userKey = 'sentient_inbox_user';
  }

  // Get stored token
  getToken() {
    return localStorage.getItem(this.tokenKey);
  }

  // Get current user
  getCurrentUser() {
    const userJson = localStorage.getItem(this.userKey);
    return userJson ? JSON.parse(userJson) : null;
  }

  // Check if user is authenticated
  isAuthenticated() {
    return !!this.getToken();
  }

  // Check if user has a specific permission
  hasPermission(permission) {
    const user = this.getCurrentUser();
    return user && user.permissions && user.permissions.includes(permission);
  }

  // Login with username/password
  async login(username, password) {
    try {
      const response = await fetch(`${this.baseUrl}/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: new URLSearchParams({
          username,
          password
        })
      });

      if (!response.ok) {
        throw new Error('Authentication failed');
      }

      const tokenData = await response.json();
      localStorage.setItem(this.tokenKey, tokenData.access_token);
      
      // Fetch user profile
      const user = await this.fetchUserProfile();
      return user;
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  }

  // Fetch user profile
  async fetchUserProfile() {
    try {
      const response = await fetch(`${this.baseUrl}/me`, {
        headers: {
          'Authorization': `Bearer ${this.getToken()}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to fetch user profile');
      }

      const user = await response.json();
      localStorage.setItem(this.userKey, JSON.stringify(user));
      return user;
    } catch (error) {
      console.error('Profile fetch error:', error);
      throw error;
    }
  }

  // Logout
  logout() {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.userKey);
  }

  // Get available OAuth providers
  async getOAuthProviders() {
    try {
      const response = await fetch(`${this.baseUrl}/oauth/providers`);
      if (!response.ok) {
        throw new Error('Failed to fetch OAuth providers');
      }
      return await response.json();
    } catch (error) {
      console.error('OAuth providers error:', error);
      throw error;
    }
  }

  // Start OAuth flow
  async initiateOAuth(provider, redirectUri) {
    try {
      const response = await fetch(`${this.baseUrl}/oauth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          provider,
          redirect_uri: redirectUri
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to initiate ${provider} login`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('OAuth initiation error:', error);
      throw error;
    }
  }

  // Process OAuth callback
  async processOAuthCallback(provider, code, redirectUri) {
    try {
      const response = await fetch(`${this.baseUrl}/oauth/callback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          provider,
          code,
          redirect_uri: redirectUri
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to process ${provider} callback`);
      }

      const data = await response.json();
      localStorage.setItem(this.tokenKey, data.access_token);
      localStorage.setItem(this.userKey, JSON.stringify(data.user));
      return data;
    } catch (error) {
      console.error('OAuth callback error:', error);
      throw error;
    }
  }
}

export const authService = new AuthService();
```

### Implementing OAuth Login

Create a component to handle OAuth authentication:

```javascript
// src/components/OAuthLogin.js
import React, { useEffect, useState } from 'react';
import { authService } from '../services/auth.service';

export function OAuthLogin() {
  const [providers, setProviders] = useState({});
  const redirectUri = `${window.location.origin}/oauth-callback`;

  useEffect(() => {
    // Fetch available providers on component mount
    async function fetchProviders() {
      try {
        const data = await authService.getOAuthProviders();
        setProviders(data.providers);
      } catch (error) {
        console.error('Failed to load providers:', error);
      }
    }
    
    fetchProviders();
  }, []);

  async function handleOAuthLogin(provider) {
    try {
      const data = await authService.initiateOAuth(provider, redirectUri);
      // Redirect to provider's authorization page
      window.location.href = data.authorization_url;
    } catch (error) {
      console.error(`${provider} login failed:`, error);
    }
  }

  return (
    <div className="oauth-buttons">
      {Object.entries(providers).map(([key, name]) => (
        <button 
          key={key} 
          onClick={() => handleOAuthLogin(key)}
          className={`oauth-btn oauth-${key}`}
        >
          Login with {name}
        </button>
      ))}
    </div>
  );
}
```

Create an OAuth callback handler component:

```javascript
// src/components/OAuthCallback.js
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '../services/auth.service';

export function OAuthCallback() {
  const [status, setStatus] = useState('Processing your login...');
  const navigate = useNavigate();

  useEffect(() => {
    async function processCallback() {
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const provider = sessionStorage.getItem('oauth_provider') || 'google'; // Default to Google if not specified
        
        if (!code) {
          setStatus('Error: No authorization code received');
          return;
        }
        
        const redirectUri = `${window.location.origin}/oauth-callback`;
        await authService.processOAuthCallback(provider, code, redirectUri);
        
        // Success - redirect to dashboard
        setStatus('Login successful! Redirecting...');
        setTimeout(() => navigate('/dashboard'), 1000);
      } catch (error) {
        console.error('OAuth callback processing failed:', error);
        setStatus(`Error: ${error.message}`);
      }
    }
    
    processCallback();
  }, [navigate]);

  return (
    <div className="oauth-callback">
      <h2>OAuth Authentication</h2>
      <p>{status}</p>
    </div>
  );
}
```

## API Service Implementation

Create a base API service to handle authenticated requests:

```javascript
// src/services/api.service.js
import { authService } from './auth.service';

export class ApiService {
  constructor() {
    this.baseUrl = 'http://localhost:8000'; // or your production API URL
  }

  // Helper method for making authenticated requests
  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    
    // Add authorization header if user is authenticated
    if (authService.isAuthenticated()) {
      options.headers = {
        ...options.headers,
        'Authorization': `Bearer ${authService.getToken()}`
      };
    }
    
    // Default headers
    options.headers = {
      'Content-Type': 'application/json',
      ...options.headers
    };
    
    try {
      const response = await fetch(url, options);
      
      // Handle rate limiting
      if (response.status === 429) {
        const retryAfter = response.headers.get('Retry-After') || 30;
        console.warn(`Rate limit exceeded. Retry after ${retryAfter} seconds.`);
        throw new Error(`Rate limit exceeded. Please try again in ${retryAfter} seconds.`);
      }
      
      // Handle authentication errors
      if (response.status === 401) {
        authService.logout();
        window.location.href = '/login?session_expired=true';
        throw new Error('Your session has expired. Please log in again.');
      }
      
      // Handle other errors
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'An error occurred');
      }
      
      // Return successful response
      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  // GET request
  get(endpoint) {
    return this.request(endpoint);
  }

  // POST request
  post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  // PUT request
  put(endpoint, data) {
    return this.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data)
    });
  }

  // DELETE request
  delete(endpoint) {
    return this.request(endpoint, {
      method: 'DELETE'
    });
  }
}

export const apiService = new ApiService();
```

## Email Service Implementation

```javascript
// src/services/email.service.js
import { apiService } from './api.service';

export class EmailService {
  // Get paginated emails with optional filtering
  getEmails(limit = 20, offset = 0, category = null) {
    let query = `?limit=${limit}&offset=${offset}`;
    if (category) {
      query += `&category=${encodeURIComponent(category)}`;
    }
    return apiService.get(`/emails${query}`);
  }

  // Get detailed email information
  getEmailDetails(messageId) {
    return apiService.get(`/emails/${messageId}`);
  }

  // Analyze email content
  analyzeEmail(content, subject, sender, messageId = null) {
    return apiService.post('/emails/analyze', {
      content,
      subject,
      sender,
      message_id: messageId
    });
  }

  // Get email processing stats
  getProcessingStats() {
    return apiService.get('/emails/stats');
  }

  // Get email settings
  getSettings() {
    return apiService.get('/emails/settings');
  }

  // Update email settings
  updateSettings(settings) {
    return apiService.put('/emails/settings', settings);
  }

  // Trigger batch processing
  processBatch(batchSize = 50) {
    return apiService.post(`/emails/process-batch?batch_size=${batchSize}`);
  }
}

export const emailService = new EmailService();
```

## Dashboard Service Implementation

```javascript
// src/services/dashboard.service.js
import { apiService } from './api.service';

export class DashboardService {
  // Get dashboard statistics
  getDashboardStats(period = 'day') {
    return apiService.get(`/dashboard/stats?period=${period}`);
  }

  // Get user activity summary
  getUserActivity() {
    return apiService.get('/dashboard/user-activity');
  }

  // Get email account statistics
  getEmailAccountStats() {
    return apiService.get('/dashboard/email-accounts');
  }

  // Get comprehensive dashboard summary
  getDashboardSummary(period = 'day') {
    return apiService.get(`/dashboard/summary?period=${period}`);
  }
}

export const dashboardService = new DashboardService();
```

## Example Components for Common Use Cases

### Email List Component

```javascript
// src/components/EmailList.js
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { emailService } from '../services/email.service';

export function EmailList() {
  const [emails, setEmails] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(0);
  const [category, setCategory] = useState(null);
  const limit = 20;

  useEffect(() => {
    async function fetchEmails() {
      try {
        setLoading(true);
        const offset = page * limit;
        const response = await emailService.getEmails(limit, offset, category);
        setEmails(response.emails);
        setTotal(response.total);
        setError(null);
      } catch (error) {
        setError('Failed to load emails: ' + error.message);
      } finally {
        setLoading(false);
      }
    }
    
    fetchEmails();
  }, [page, category]);

  // Format date to more readable format
  function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  }

  return (
    <div className="email-list">
      <h2>Processed Emails</h2>
      
      {/* Category filter */}
      <div className="filters">
        <select 
          value={category || ''} 
          onChange={e => setCategory(e.target.value || null)}
        >
          <option value="">All Categories</option>
          <option value="Meeting">Meetings</option>
          <option value="Update">Updates</option>
          <option value="Request">Requests</option>
          <option value="Notification">Notifications</option>
        </select>
      </div>
      
      {loading && <p>Loading...</p>}
      {error && <p className="error">{error}</p>}
      
      {!loading && !error && (
        <>
          <table className="email-table">
            <thead>
              <tr>
                <th>Subject</th>
                <th>Sender</th>
                <th>Received</th>
                <th>Category</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {emails.map(email => (
                <tr key={email.message_id}>
                  <td>
                    <Link to={`/emails/${email.message_id}`}>
                      {email.subject}
                    </Link>
                  </td>
                  <td>{email.sender}</td>
                  <td>{formatDate(email.received_at)}</td>
                  <td>
                    <span className={`category ${email.category.toLowerCase()}`}>
                      {email.category}
                    </span>
                  </td>
                  <td>
                    {email.is_responded ? 
                      <span className="status responded">Responded</span> : 
                      <span className="status pending">Pending</span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          
          {/* Pagination */}
          <div className="pagination">
            <button 
              disabled={page === 0} 
              onClick={() => setPage(p => p - 1)}
            >
              Previous
            </button>
            <span>
              Page {page + 1} of {Math.ceil(total / limit)}
            </span>
            <button 
              disabled={page >= Math.ceil(total / limit) - 1} 
              onClick={() => setPage(p => p + 1)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}
```

### Dashboard Overview Component

```javascript
// src/components/DashboardOverview.js
import React, { useEffect, useState } from 'react';
import { dashboardService } from '../services/dashboard.service';
// Assuming you're using a charting library like Chart.js with React
import { Bar, Pie } from 'react-chartjs-2';

export function DashboardOverview() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [period, setPeriod] = useState('day');

  useEffect(() => {
    async function fetchDashboardData() {
      try {
        setLoading(true);
        const data = await dashboardService.getDashboardSummary(period);
        setSummary(data);
        setError(null);
      } catch (error) {
        setError('Failed to load dashboard data: ' + error.message);
      } finally {
        setLoading(false);
      }
    }
    
    fetchDashboardData();
  }, [period]);

  if (loading) return <p>Loading dashboard...</p>;
  if (error) return <p className="error">{error}</p>;
  if (!summary) return null;

  // Prepare data for charts
  const volumeChartData = {
    labels: summary.stats.volume_trend.map(item => item.date),
    datasets: [
      {
        label: 'Meeting Emails',
        data: summary.stats.volume_trend.map(item => item.meeting),
        backgroundColor: 'rgba(54, 162, 235, 0.6)',
      },
      {
        label: 'Other Emails',
        data: summary.stats.volume_trend.map(item => item.other),
        backgroundColor: 'rgba(255, 99, 132, 0.6)',
      }
    ]
  };

  const categoryChartData = {
    labels: summary.stats.category_distribution.map(item => item.category),
    datasets: [
      {
        data: summary.stats.category_distribution.map(item => item.count),
        backgroundColor: [
          'rgba(54, 162, 235, 0.6)',
          'rgba(255, 99, 132, 0.6)',
          'rgba(255, 206, 86, 0.6)',
          'rgba(75, 192, 192, 0.6)',
          'rgba(153, 102, 255, 0.6)',
        ],
      }
    ]
  };

  return (
    <div className="dashboard-overview">
      <h2>Dashboard Overview</h2>
      
      {/* Time period selector */}
      <div className="period-selector">
        <label>Time Period:</label>
        <select value={period} onChange={e => setPeriod(e.target.value)}>
          <option value="day">Today</option>
          <option value="week">This Week</option>
          <option value="month">This Month</option>
        </select>
      </div>
      
      {/* Key metrics */}
      <div className="metrics-grid">
        <div className="metric-card">
          <h3>Total Emails</h3>
          <div className="metric-value">{summary.stats.total_emails}</div>
        </div>
        <div className="metric-card">
          <h3>Meeting Emails</h3>
          <div className="metric-value">{summary.stats.meeting_emails}</div>
        </div>
        <div className="metric-card">
          <h3>Response Rate</h3>
          <div className="metric-value">{(summary.stats.response_rate * 100).toFixed(1)}%</div>
        </div>
        <div className="metric-card">
          <h3>Success Rate</h3>
          <div className="metric-value">{(summary.stats.success_rate * 100).toFixed(1)}%</div>
        </div>
      </div>
      
      {/* Charts */}
      <div className="charts-container">
        <div className="chart-card">
          <h3>Email Volume Trend</h3>
          <Bar data={volumeChartData} />
        </div>
        <div className="chart-card">
          <h3>Category Distribution</h3>
          <Pie data={categoryChartData} />
        </div>
      </div>
      
      {/* User activity */}
      <div className="activity-section">
        <h3>User Activity</h3>
        <p>{summary.user_activity.active_users} active users out of {summary.user_activity.total_users} total</p>
        
        <h4>Top Email Accounts</h4>
        <ul className="account-list">
          {summary.email_accounts.slice(0, 3).map(account => (
            <li key={account.email}>
              <span className="account-email">{account.email}</span>
              <span className="account-count">{account.total_processed} emails</span>
              <span className={`account-status ${account.is_active ? 'active' : 'inactive'}`}>
                {account.is_active ? 'Active' : 'Inactive'}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
```

## Permission-Based UI Implementation

Create a wrapper component to handle permissions:

```javascript
// src/components/ProtectedRoute.js
import React from 'react';
import { Navigate } from 'react-router-dom';
import { authService } from '../services/auth.service';

export function ProtectedRoute({ children, requiredPermission }) {
  const isAuthenticated = authService.isAuthenticated();
  
  // Check if user is authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  // If a specific permission is required, check for it
  if (requiredPermission) {
    const hasPermission = authService.hasPermission(requiredPermission);
    if (!hasPermission) {
      return <Navigate to="/unauthorized" replace />;
    }
  }
  
  // User is authenticated and has permission, render the children
  return children;
}
```

Use the ProtectedRoute component in your routes:

```javascript
// src/App.js
import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Login } from './components/Login';
import { OAuthCallback } from './components/OAuthCallback';
import { Dashboard } from './components/Dashboard';
import { EmailList } from './components/EmailList';
import { EmailDetails } from './components/EmailDetails';
import { Settings } from './components/Settings';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Unauthorized } from './components/Unauthorized';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/oauth-callback" element={<OAuthCallback />} />
        <Route path="/unauthorized" element={<Unauthorized />} />
        
        <Route path="/" element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } />
        
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } />
        
        <Route path="/emails" element={
          <ProtectedRoute requiredPermission="view">
            <EmailList />
          </ProtectedRoute>
        } />
        
        <Route path="/emails/:messageId" element={
          <ProtectedRoute requiredPermission="view">
            <EmailDetails />
          </ProtectedRoute>
        } />
        
        <Route path="/settings" element={
          <ProtectedRoute requiredPermission="admin">
            <Settings />
          </ProtectedRoute>
        } />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
```

## Error Handling Best Practices

1. Implement a global error handler component:

```javascript
// src/components/ErrorBoundary.js
import React, { Component } from 'react';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Error caught by ErrorBoundary:", error, errorInfo);
    // Optionally log to an error reporting service
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-container">
          <h2>Something went wrong</h2>
          <p>{this.state.error && this.state.error.toString()}</p>
          <button onClick={() => window.location.reload()}>Reload Page</button>
        </div>
      );
    }

    return this.props.children;
  }
}
```

2. Create reusable error alert components:

```javascript
// src/components/ErrorAlert.js
import React from 'react';

export function ErrorAlert({ message, onDismiss }) {
  if (!message) return null;
  
  return (
    <div className="error-alert">
      <div className="error-message">{message}</div>
      {onDismiss && (
        <button className="dismiss-btn" onClick={onDismiss}>
          ×
        </button>
      )}
    </div>
  );
}
```

## Testing the Integration

Before deploying to production, thoroughly test your frontend integration:

1. **Authentication Flows:** Test both password and OAuth authentication
2. **Data Retrieval:** Verify that data is properly fetched and displayed
3. **Error Handling:** Test error conditions and verify proper user feedback
4. **Permissions:** Ensure protected routes work as expected
5. **Form Submissions:** Test all forms that submit data to the API

## Best Practices for Frontend Integration

1. **Keep authentication state in a central service** for consistent access across components
2. **Use appropriate error handling** at both the global and component levels
3. **Implement loading states** to provide feedback during API calls
4. **Cache frequently accessed data** to reduce API calls
5. **Implement proper pagination** for large data sets
6. **Use debouncing** for search and filter operations
7. **Implement progressive enhancement** when possible
8. **Follow the principle of least privilege** - only request resources the user has permission to access

## Common Integration Issues and Solutions

1. **CORS issues**: Ensure your backend allows requests from your frontend origin
2. **Token expiration**: Implement proper token refresh mechanisms
3. **Rate limiting**: Implement backoff strategies for rate-limited requests
4. **Performance**: Use pagination, limit requested fields, and implement caching
5. **Security**: Never store sensitive information in local storage or client-side code
