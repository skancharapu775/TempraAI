# 📧 Email Features Documentation

## Overview

The TempraAI app now includes comprehensive email functionality that works with both Gmail and Outlook. After the email intent is declared, the system automatically routes to specific email functions based on user requests.

## 🚀 Email Functions

### 1. **Email Summarization**
- **Command**: "Summarize my recent emails"
- **Function**: Analyzes recent emails and provides a concise summary
- **Features**:
  - Identifies key themes and topics
  - Highlights important emails needing attention
  - Shows urgent matters
  - Provides overall email volume patterns

### 2. **Priority Email Management**
- **Command**: "Show me high priority emails"
- **Function**: Retrieves and displays important emails
- **Features**:
  - Filters by importance/priority flags
  - Shows email details with priority indicators
  - Displays sender, subject, and snippets

### 3. **Email Organization**
- **Command**: "Create a Work folder" or "Organize my emails"
- **Function**: Creates folders/labels and organizes emails
- **Features**:
  - Creates new folders/labels
  - Auto-organizes emails based on content
  - Supports custom organization criteria

### 4. **Email Search**
- **Command**: "Search for emails about meetings"
- **Function**: Searches emails by keywords or criteria
- **Features**:
  - Full-text search across emails
  - Configurable result limits
  - Search within specific folders

### 5. **Email Composition**
- **Command**: "Compose an email to john@example.com about the project"
- **Function**: Creates new email drafts
- **Features**:
  - Extracts recipient, subject, and body
  - Supports attachments and folders
  - Priority settings
  - Confirmation workflow

### 6. **Draft Management**
- **Command**: "Show my email drafts"
- **Function**: Lists and manages email drafts
- **Features**:
  - Shows all pending drafts
  - Displays draft details
  - Draft management options

### 7. **Email Scheduling**
- **Command**: "Schedule an email to be sent tomorrow"
- **Function**: Schedules emails for future sending
- **Features**:
  - Future delivery scheduling
  - Time-based sending
  - Scheduled email management

## 🔧 Technical Implementation

### Email Service Architecture

```python
# Create email handler for specific provider
email_handler = create_email_handler("gmail")  # or "outlook"

# Handle email intent with automatic function classification
reply, pending_changes, show_accept_deny = await email_handler.handle_email_intent(message)
```

### Supported Providers

#### Gmail API
- **Authentication**: OAuth 2.0 with Google
- **Features**: Full CRUD operations, labels, search
- **Setup**: Requires `gmail_credentials.json` and `gmail_token.json`

#### Microsoft Graph API (Outlook)
- **Authentication**: OAuth 2.0 with Microsoft Identity
- **Features**: Full CRUD operations, folders, search
- **Setup**: Requires Azure app registration with client credentials

### Environment Variables

```bash
# OpenAI API
OPENAI_API_KEY=your_openai_key

# Microsoft Graph (for Outlook)
MS_TENANT_ID=your_tenant_id
MS_CLIENT_ID=your_client_id
MS_CLIENT_SECRET=your_client_secret
```

## 📱 Mobile & Web Support

The email functionality works seamlessly across both mobile and web platforms:

### Frontend Integration
- **Unified API**: Same endpoints for mobile and web
- **Responsive Design**: Optimized for all screen sizes
- **Real-time Updates**: Live email status updates

### Backend Features
- **Async Processing**: Non-blocking email operations
- **Error Handling**: Graceful failure management
- **Rate Limiting**: API quota management
- **Caching**: Performance optimization

## 🎯 Usage Examples

### Basic Email Operations
```
User: "Summarize my recent emails"
AI: "📧 Email Summary: You have 15 new emails. 3 are high priority from your boss about the quarterly review..."

User: "Show me high priority emails"
AI: "🎯 High Priority Emails (5 found): 1. 🔴 Quarterly Review Meeting..."

User: "Create a Work folder"
AI: "✅ Created new folder: Work"
```

### Advanced Email Operations
```
User: "Compose an email to john@example.com about the project deadline"
AI: "📧 Email Details: Subject: Project Deadline Update, To: john@example.com..."

User: "Schedule an email to be sent tomorrow at 9 AM"
AI: "📅 Email scheduled for tomorrow at 9:00 AM"
```

## 🔒 Security & Privacy

- **OAuth 2.0**: Secure authentication
- **Token Management**: Automatic token refresh
- **Data Encryption**: End-to-end security
- **Access Control**: User-specific permissions

## 🚀 Future Enhancements

- **Smart Categorization**: AI-powered email organization
- **Auto-Reply**: Intelligent response suggestions
- **Email Analytics**: Usage patterns and insights
- **Integration**: Calendar and contact sync
- **Voice Commands**: Voice-to-email functionality

## 🧪 Testing

Run the test script to verify functionality:

```bash
cd backend
python test_emails.py
```

This will test all email functions and provide feedback on their operation. 