const { app, BrowserWindow, globalShortcut } = require('electron');
const path = require('path');

let mainWindow;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 360,
        height: 580,
        x: 50,
        y: 50,
        frame: false,           // No window chrome
        transparent: true,      // Transparent background
        alwaysOnTop: true,      // Float above other windows
        resizable: true,
        skipTaskbar: false,     // Show in taskbar
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true
        },
        icon: path.join(__dirname, 'icon.png')
    });

    mainWindow.loadFile('index.html');

    // Allow dragging the window by the header
    mainWindow.setMovable(true);

    // Close on escape (optional)
    mainWindow.webContents.on('before-input-event', (event, input) => {
        if (input.key === 'Escape') {
            mainWindow.minimize();
        }
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

app.whenReady().then(() => {
    createWindow();

    // Global shortcut to show/hide (Ctrl+Shift+C)
    globalShortcut.register('CommandOrControl+Shift+C', () => {
        if (mainWindow) {
            if (mainWindow.isVisible()) {
                mainWindow.hide();
            } else {
                mainWindow.show();
                mainWindow.focus();
            }
        }
    });

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    globalShortcut.unregisterAll();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
