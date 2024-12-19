# Totoro Log Scenario Finder

**Totoro** is a log analysis tool that reads log files within a specified directory and searches for scenarios defined in a configuration file. It produces a CSV report flagging all found matches.

## Features

- Analyze multiple log files simultaneously.  
- Define custom search scenarios using a JSON configuration file.  
- Supports regular expressions for advanced matching.  
- Generates a detailed CSV report.  
- User-friendly GUI with progress tracking and cancellation option.

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/OmerNachmani/totoro-log-analyzer.git
   cd totoro-log-analyzer
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**

   ```bash
   python main.py
   ```

## Building the Executable

To build a standalone executable using **PyInstaller**, run:

```bash
pyinstaller --onedir --windowed --icon=app.ico --add-data "app.ico;." main.py
```

The executable will be created in the `dist` directory.

## Usage

1. **Select a Log Directory** containing `.log` files.  
2. **Choose a Config File** (`scenario.json`) that defines the search patterns.  
3. Click **"Start Analysis"** to begin.  
4. The tool will generate a CSV report in the current directory.

### Example Configuration File (`scenario.json`)

```json
{
    "scenarios": [
        {
            "name": "CONNECTED to good SSID",
            "use_regex": false,
            "start_pattern": "[ATTEMPT_TO_CONNECT]",
            "end_pattern": "CONNECTED - to:",
            "lines_between_start_to_end": [
                "SSID Name: 'Best_SSID_Ever'",
                "SSID Name: 'I'm also a nice SSID'"
            ],
            "mandatory_logic": "OR",
            "success_message": "Matched rule",
            "fail_message": "Violates rule",
            "include_fails": false
        }
    ]
}
```

## Contributing

Contributions are welcome! If you have ideas or improvements, feel free to submit a pull request.

## License

This project is licensed under the **MIT License**.
