# Power BI Tray Monitor

A Windows system tray application for monitoring Power BI semantic model refresh status, capacity utilization, and gateway health - all at a glance.

## ✨ Features

### Dynamic Tray Icon
The tray icon displays **real-time capacity metrics** using 3 dynamic bars:

| Bar | Represents | Color |
|-----|------------|-------|
| Left | Background utilization % | Blue |
| Middle | Total utilization % | Green/Orange/Red (health) |
| Right | Interactive utilization % | Teal |

The middle bar changes color based on capacity health:
- 🟢 **Green**: Normal (<80%)
- 🟠 **Orange**: High (80-99%)
- 🔴 **Red**: Critical (≥100%, throttling)

### Refresh Monitoring
- ✅ Real-time refresh status tracking
- 📊 Detailed refresh history with table-level breakdown
- ⏱️ Countdown to next scheduled refresh
- 🔔 Windows notifications on refresh completion/failure

### Capacity Metrics
- 📈 Live capacity utilization monitoring
- 🔵 Background vs Interactive utilization breakdown
- ⚡ Throttling status alerts
- 📊 Stacked progress bar visualization

### Gateway Health
- 🌐 Gateway online/offline status
- ⚠️ Alerts for offline or degraded gateways
- 📍 Multi-gateway support with individual status

### Pipeline Integration
- 🔄 Azure Data Factory pipeline schedule tracking
- ⏰ Next run time display for each pipeline
- 📋 Full/Partial refresh type indicators

## 🚀 Quick Start

### Automated Setup (Recommended)

1. **Download or clone** this repository
2. **Double-click `setup.bat`** - this will:
   - Create a Python virtual environment
   - Install all dependencies
   - Optionally add to Windows startup
   - Launch the application

### Manual Setup

```powershell
# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run the application
python -m pbi_tray
```

## ⚙️ Configuration

### First Run
1. A browser window opens for **Microsoft sign-in**
2. Sign in with your Power BI account
3. Credentials are cached for future sessions

### Settings
Right-click the tray icon → **Settings** to configure:

| Setting | Description |
|---------|-------------|
| **Workspace ID** | Your Power BI workspace GUID |
| **Dataset ID** | Your semantic model GUID |
| **Timezone** | Display timezone for timestamps |
| **Capacity Workspace** | Workspace for capacity metrics (optional) |
| **Pipelines** | Azure Data Factory pipeline configuration |

### Configuration File
Copy `settings.example.json` to `settings.json` and configure your IDs:

```json
{
    "workspace_id": "your-workspace-guid",
    "dataset_id": "your-dataset-guid",
    "refresh_interval": 300,
    "timezone": "UTC",
    "capacity_metrics_workspace": "Microsoft Fabric Capacity Metrics - YourCapacity"
}
```

### Finding Your IDs

1. Open [Power BI Service](https://app.powerbi.com)
2. Navigate to your workspace → semantic model
3. Look at the URL:
   ```
   https://app.powerbi.com/groups/{WORKSPACE_ID}/datasets/{DATASET_ID}/details
   ```

## 📱 System Tray Menu

Right-click the tray icon:

| Section | Items |
|---------|-------|
| **Status** | Current status, last refresh time, duration |
| **Recent History** | Last 5 refreshes with expandable details |
| **Capacity** | Utilization %, BG/Interactive breakdown |
| **Actions** | Trigger Refresh, Cancel Refresh, Check Status |
| **Account** | Sign In, Sign Out |
| **Settings** | Timezone, Configuration |

## 🖥️ Details Window

Double-click the tray icon to open the full details window:

- **Status Overview**: Last refresh with countdown to next
- **Gateways**: Health status of all connected gateways
- **Pipelines**: Configured refresh pipelines with schedules
- **Capacity**: Detailed utilization with stacked bar chart
- **History**: Scrollable list with expandable table-level details

## 🔧 Advanced Configuration

### Capacity Metrics
To enable capacity monitoring, you need access to a workspace with the **Microsoft Fabric Capacity Metrics** app installed.

1. Install the [Capacity Metrics app](https://appsource.microsoft.com/en-us/product/power-bi/pbi_pcmm.microsoftpremiumfabricpreviewreport)
2. Copy the workspace ID where it's installed
3. Add to settings as "Capacity Workspace"

### Pipeline Configuration
Configure Azure Data Factory pipelines in settings:

```json
{
  "pipelines": {
    "pipeline-guid-1": {
      "name": "Full Daily Refresh",
      "type": "full",
      "cron": "0 6 * * *"
    },
    "pipeline-guid-2": {
      "name": "Intra-Daily Refresh", 
      "type": "partial",
      "cron": "0 */2 * * *"
    }
  }
}
```

## 📁 Project Structure

```
PowerBI_Tray/
├── pbi_tray/              # Main application package
│   ├── api/               # Power BI API clients
│   ├── ui/                # UI components
│   ├── __init__.py
│   ├── __main__.py        # Entry point
│   ├── auth.py            # Authentication
│   ├── config.py          # Configuration
│   └── tray.py            # System tray
├── assets/                # Icons and images
│   ├── icon.ico
│   ├── PBI_mini.png
│   ├── settings.png
│   └── ...
├── scripts/               # Utility scripts
│   ├── add_to_startup.bat
│   ├── remove_from_startup.bat
│   └── pbi_tray_silent.vbs
├── setup.bat              # Automated setup (double-click)
├── setup.ps1              # PowerShell setup script
├── settings.json          # User configuration (gitignored)
├── settings.example.json  # Example configuration
├── requirements.txt       # Python dependencies
└── README.md
```

## 🔒 Authentication

Uses MSAL (Microsoft Authentication Library):

- **First run**: Browser-based interactive sign-in
- **Subsequent runs**: Automatic token refresh
- **Token cache**: Securely stored in `.token_cache.json`

To force re-authentication: **Account → Sign Out**

## 📋 Requirements

- **OS**: Windows 10/11
- **Python**: 3.9+
- **License**: Power BI Pro or Premium Per User
- **Permissions**: Read access to workspace/dataset

## 🐛 Troubleshooting

### Icon not appearing
- Check system tray overflow (arrow near clock)
- Restart the application

### Authentication issues
- Use **Account → Sign Out**, then sign in again
- Delete `.token_cache.json` and restart

### Capacity metrics unavailable
- Ensure Capacity Metrics app is installed
- Verify workspace ID is correct
- Check you have access to the capacity

### "No gateway required" showing
- Dataset uses only cloud datasources
- No on-premises gateway configured

## 📄 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

Contributions welcome! Please open an issue or pull request
