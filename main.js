const { app, BrowserWindow, ipcMain, session } = require('electron');
const path = require('path');

let mainWindow;
let isLoggedIn = false;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webviewTag: true
    }
  });

  if (isLoggedIn) {
    mainWindow.loadFile('browser.html');
  } else {
    mainWindow.loadFile('login.html');
  }

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});

// Handle login
ipcMain.on('login', (event, credentials) => {
  // Simple login validation (username: user, password: pass)
  if (credentials.username === 'user' && credentials.password === 'pass') {
    isLoggedIn = true;
    event.reply('login-response', { success: true });
    mainWindow.loadFile('browser.html');
  } else {
    event.reply('login-response', { success: false, message: 'Invalid credentials' });
  }
});

// Handle logout
ipcMain.on('logout', (event) => {
  isLoggedIn = false;
  mainWindow.loadFile('login.html');
});
