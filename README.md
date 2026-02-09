# Nova Browser

A modern web browser built with Electron featuring vertical tabs and user authentication.

## Features

- **User Login System**: Secure login before accessing the browser
- **Vertical Tabs**: Tabs displayed in a sidebar for better organization
- **Modern Browser Experience**: Navigate, search, and browse the web
- **Tab Management**: Create, switch, and close tabs easily
- **Navigation Controls**: Back, forward, refresh, and URL navigation

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Lawliet2004/Nova-Browser.git
cd Nova-Browser
```

2. Install dependencies:
```bash
npm install
```

## Usage

Run the browser:
```bash
npm start
```

### Login Credentials

For the demo version, use these credentials:
- **Username**: `user`
- **Password**: `pass`

## How to Use

1. Launch the application with `npm start`
2. Log in with the provided credentials
3. Click "+ New Tab" to create a new browser tab
4. Enter a URL or search term in the address bar
5. Use the navigation buttons to browse
6. Switch between tabs using the vertical sidebar
7. Close tabs using the × button on each tab
8. Click "Logout" to return to the login screen

## Technical Details

- Built with Electron
- Uses Electron's webview tag for rendering web pages
- Custom tab management system
- Simple authentication system

## Security Considerations

This is a **demo application** with the following security considerations:

1. **Authentication**: Uses hardcoded credentials for demo purposes. In production, implement proper authentication with password hashing, database validation, or OAuth.

2. **Electron Security**: The app uses `nodeIntegration: true` and `contextIsolation: false` for simplicity. In production, these should be changed to more secure defaults with preload scripts.

3. **URL Validation**: The app validates URLs to only allow HTTP/HTTPS protocols, blocking potentially malicious protocols like `javascript:`, `data:`, and `file:`.

4. **Known Vulnerabilities**: The current Electron version (28.0.0) has a moderate severity ASAR integrity bypass vulnerability. For production use, upgrade to Electron 35.7.5 or later.

## Future Enhancements

- Bookmarks system
- History tracking
- Multiple user accounts with proper authentication
- Theme customization
- Extensions support
