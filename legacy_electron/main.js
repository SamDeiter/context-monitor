const electron = require('electron');
const app = electron.app;
const BrowserWindow = electron.BrowserWindow;
const globalShortcut = electron.globalShortcut;
const path = require('path');

let mainWindow;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 360,
        height: 600,
        x: 100,
        y: 100,
        frame: false,
        transparent: true,
        alwaysOnTop: true,
        resizable: true,
        skipTaskbar: false,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true
        }
    });

    mainWindow.loadFile('index.html');
    mainWindow.setMovable(true);

    mainWindow.on('closed', function() {
        mainWindow = null;
    });
}

app.on('ready', createWindow);

app.on('window-all-closed', function() {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', function() {
    if (mainWindow === null) {
        createWindow();
    }
});
