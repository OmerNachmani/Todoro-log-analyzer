# Totoro Log Scenario Finder

**Totoro** is a user-friendly log analysis tool designed to streamline the process of identifying patterns in large sets of log files. By allowing users to define custom search scenarios through a simple JSON configuration file, Totoro can automatically scan logs and generate a comprehensive CSV report highlighting relevant matches. Whether you're troubleshooting network issues, validating system behavior, or searching for specific log patterns, Totoro simplifies the task with its intuitive interface and robust capabilities.

## How It Works
Totoro works by recursively scanning log files within a specified directory. It looks for predefined patterns (start patterns, end patterns, and lines between) that you specify in a configuration file (scenario.json). Each scenario in the configuration file defines a specific pattern or condition to match, including optional use of regular expressions for advanced searches.

When a match is found, Totoro logs the details in a CSV report, making it easy to review and analyze results. The tool supports real-time progress tracking and the ability to cancel long-running operations.

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
The configuration file defines the patterns Totoro will search for in the log files. Here’s an example:
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
### Explanation of the Example

This configuration defines a single scenario named **"CONNECTED to good SSID"**. Here’s a breakdown of what each field means:

- **`name`**: Descriptive name for the scenario.  
- **`use_regex`**: Set to `false`, meaning the tool will use simple string matching instead of regular expressions.  
- **`start_pattern`**: The scenario starts when the line contains `[ATTEMPT_TO_CONNECT]`.  
- **`end_pattern`**: The scenario ends when the line contains `CONNECTED - to:`.  
- **`lines_between_start_to_end`**: Specifies lines that must appear between the start and end patterns. In this example, it looks for one of the following lines:  
  - `SSID Name: 'Best_SSID_Ever'`  
  - `SSID Name: 'I'm also a nice SSID'`  
- **`mandatory_logic`**: Set to `"OR"`, meaning at least one of the specified lines must be present for the scenario to be considered a match.  
- **`success_message`**: The message added to the CSV when the scenario matches (`"Matched rule"`).  
- **`fail_message`**: The message added when the scenario does not match (`"Violates rule"`).  
- **`include_fails`**: Set to `false`, meaning only successful matches will be included in the CSV report.

### How This Works in Practice

When Totoro scans a log file, it will:

1. Look for a line containing `[ATTEMPT_TO_CONNECT]` (start pattern).  
2. Between the start pattern and a line containing `CONNECTED - to:` (end pattern), it will check if any of the lines match:  
   - `SSID Name: 'Best_SSID_Ever'`  
   - `SSID Name: 'I'm also a nice SSID'`  
3. If either of those lines appears, it logs the scenario as **"Matched rule"**.  
4. If not, it logs **"Violates rule"** (unless `include_fails` is set to `false`).


## Contributing

Contributions are welcome! If you have ideas or improvements, feel free to submit a pull request.

## License

This project is licensed under the **MIT License**.
