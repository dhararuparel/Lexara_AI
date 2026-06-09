const { app, BrowserWindow, Menu, shell, ipcMain } = require('electron');
const path = require('path');

// Maintain a global reference of the window object to prevent garbage collection
let mainWindow;

// Define production target URL. Can be overridden using LEXARA_URL env variable
const LEXARA_URL = process.env.LEXARA_URL || 'https://lexara-ai.vercel.app';

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'Lexara AI',
    icon: path.join(__dirname, 'assets', 'icon.ico'),
    webPreferences: {
      nodeIntegration: false,      // Security: Disable Node.js integration in renderer
      contextIsolation: true,     // Security: Separate execution contexts
      sandbox: true,              // Security: Run renderer in utility process sandbox
      preload: path.join(__dirname, 'preload.js') // Optional preload script for custom APIs
    }
  });

  // Load the target URL
  mainWindow.loadURL(LEXARA_URL);

  // Security: Handle navigation events to prevent unauthorized redirects
  mainWindow.webContents.on('will-navigate', (event, navigationUrl) => {
    const parsedUrl = new URL(navigationUrl);
    const targetHost = parsedUrl.host;
    const prodHost = new URL(LEXARA_URL).host;

    // Only allow navigation within the same domain
    if (targetHost !== prodHost && !targetHost.includes('google.com') && !targetHost.includes('github.com')) {
      event.preventDefault();
      shell.openExternal(navigationUrl); // Open external links in default system browser
    }
  });

  // Security: Prevent creation of new windows containing arbitrary code
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    const parsedUrl = new URL(url);
    const targetHost = parsedUrl.host;
    const prodHost = new URL(LEXARA_URL).host;

    if (targetHost === prodHost) {
      return { action: 'allow' }; // Allow workspace invite / reset password / shared chats inside app
    }
    
    // Otherwise open in native browser
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Prevent drag-and-drop from navigating the entire window to a file path
  mainWindow.webContents.on('will-prevent-unload', (event) => {
    event.preventDefault();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Custom Native Application Menu
function createApplicationMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'New Chat',
          accelerator: 'CmdOrCtrl+N',
          click: () => {
            mainWindow.webContents.executeJavaScript("document.getElementById('newChatBtn')?.click()");
          }
        },
        { type: 'separator' },
        { role: 'quit' }
      ]
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'zoom' },
        { type: 'separator' },
        { role: 'front' }
      ]
    },
    {
      role: 'help',
      submenu: [
        {
          label: 'About Lexara AI',
          click: () => {
            mainWindow.webContents.executeJavaScript("if (typeof openAbout === 'function') openAbout();");
          }
        },
        {
          label: 'Learn More',
          click: async () => {
            await shell.openExternal('https://lexara.ai');
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// App Initialization
app.whenReady().then(() => {
  createMainWindow();
  createApplicationMenu();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

// App Quit
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Auto-Update preparation stub
// To enable, install electron-updater and configure a remote feed
/*
const { autoUpdater } = require("electron-updater");
app.on('ready', () => {
  autoUpdater.checkForUpdatesAndNotify();
});
*/
