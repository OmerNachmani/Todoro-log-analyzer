import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import json
import csv
from pathlib import Path
from threading import Thread, Event
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import re
import queue

# Function to get the absolute path to bundled resources (for PyInstaller)
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def load_config(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def match_pattern(line, pattern, use_regex, compiled_regex=None):
    if use_regex:
        return compiled_regex.search(line) is not None
    else:
        return pattern in line

def process_log_file(file_path, scenario, results_queue, cancel_event):
    use_regex = scenario.get('use_regex', False)
    start_pattern = scenario['start_pattern']
    end_pattern = scenario['end_pattern']
    mandatory_patterns = scenario['lines_between_start_to_end']
    mandatory_logic = scenario.get('mandatory_logic', 'OR').upper()
    include_fails = scenario.get('include_fails', True)

    # Compile regexes if needed
    start_regex = re.compile(start_pattern) if use_regex else None
    end_regex = re.compile(end_pattern) if use_regex else None
    mandatory_regexes = [re.compile(p) for p in mandatory_patterns] if use_regex else None

    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            have_first = False
            first_line_no = None
            first_line_text = None
            found_patterns = set() if mandatory_logic == 'AND' else None
            found_line_info = {}

            for line_number, line in enumerate(f, start=1):
                if cancel_event.is_set():
                    return

                line_stripped = line.strip()

                start_matched = match_pattern(line, start_pattern, use_regex, start_regex)

                if not have_first and start_matched:
                    have_first = True
                    first_line_no = line_number
                    first_line_text = line_stripped

                    if mandatory_logic == 'AND':
                        found_patterns = set()
                    found_line_info = {}

                    # Check mandatory patterns on the same line
                    if use_regex:
                        for pattern_regex, pattern_str in zip(mandatory_regexes, mandatory_patterns):
                            if pattern_regex.search(line):
                                found_line_info[line_number] = line_stripped
                                if mandatory_logic == 'OR':
                                    break
                                else:
                                    found_patterns.add(pattern_regex)
                    else:
                        for pattern_str in mandatory_patterns:
                            if pattern_str in line:
                                found_line_info[line_number] = line_stripped
                                if mandatory_logic == 'OR':
                                    break
                                else:
                                    found_patterns.add(pattern_str)

                    # Check end pattern on the same line
                    end_matched = match_pattern(line, end_pattern, use_regex, end_regex)
                    if end_matched:
                        if mandatory_logic == 'OR':
                            success = len(found_line_info) > 0
                        elif mandatory_logic == 'AND':
                            if use_regex:
                                success = found_patterns is not None and len(found_patterns) == len(mandatory_regexes)
                            else:
                                success = found_patterns is not None and len(found_patterns) == len(mandatory_patterns)
                        else:
                            success = len(found_line_info) > 0

                        result = scenario['success_message'] if success else scenario['fail_message']

                        if include_fails or success:
                            line_nos = ", ".join([str(num) for num in sorted(found_line_info.keys())])
                            lines = "; ".join(found_line_info.values())
                            results_queue.put([
                                file_path, scenario['name'], first_line_no, first_line_text,
                                line_nos, lines,
                                line_number, line_stripped, result
                            ])

                        have_first = False
                        found_patterns = set() if mandatory_logic == 'AND' else None
                        found_line_info = {}

                elif have_first:
                    if use_regex:
                        for pattern_regex, pattern_str in zip(mandatory_regexes, mandatory_patterns):
                            if pattern_regex.search(line):
                                found_line_info[line_number] = line_stripped
                                if mandatory_logic == 'OR':
                                    break
                                else:
                                    found_patterns.add(pattern_regex)
                    else:
                        for pattern_str in mandatory_patterns:
                            if pattern_str in line:
                                found_line_info[line_number] = line_stripped
                                if mandatory_logic == 'OR':
                                    break
                                else:
                                    found_patterns.add(pattern_str)

                    end_matched = match_pattern(line, end_pattern, use_regex, end_regex)
                    if end_matched:
                        if mandatory_logic == 'OR':
                            success = len(found_line_info) > 0
                        elif mandatory_logic == 'AND':
                            if use_regex:
                                success = found_patterns is not None and len(found_patterns) == len(mandatory_regexes)
                            else:
                                success = found_patterns is not None and len(found_patterns) == len(mandatory_patterns)
                        else:
                            success = len(found_line_info) > 0

                        result = scenario['success_message'] if success else scenario['fail_message']

                        if include_fails or success:
                            line_nos = ", ".join([str(num) for num in sorted(found_line_info.keys())])
                            lines = "; ".join(found_line_info.values())
                            results_queue.put([
                                file_path, scenario['name'], first_line_no, first_line_text,
                                line_nos, lines,
                                line_number, line_stripped, result
                            ])

                        have_first = False
                        found_patterns = set() if mandatory_logic == 'AND' else None
                        found_line_info = {}
    except:
        pass

def writer_thread_func(results_queue, csv_writer, cancel_event):
    while True:
        if cancel_event.is_set() and results_queue.empty():
            break

        try:
            item = results_queue.get(timeout=0.1)
        except:
            if cancel_event.is_set():
                break
            continue

        if item is None:
            break
        csv_writer.writerow(item)
        results_queue.task_done()

def analyze_logs(directory, config_file, output_file, progress_bar, status_label, start_button, cancel_event):
    try:
        config = load_config(config_file)
        scenarios = config.get('scenarios', [])
        if not scenarios:
            raise ValueError("No scenarios found in config file.")

        output_path = Path(output_file)
        with output_path.open('w', newline='') as f:
            csv_writer = csv.writer(f)
            csv_writer.writerow([
                "FilePath", "Scenario", "FirstLineNo", "FirstLine",
                "MandatoryPatternLineNos", "MandatoryPatternLines",
                "SecondLineNo", "SecondLine", "Result"
            ])

            status_label.config(text="Finding log files...")
            log_files = list(Path(directory).rglob('*.log'))
            total_files = len(log_files)

            if total_files == 0:
                raise ValueError("No log files found in the specified directory.")

            status_label.config(text=f"Found {total_files} log files. Starting analysis...")

            progress_bar['maximum'] = total_files * len(scenarios)
            processed_files = 0

            results_queue = queue.Queue()
            writer_thread = Thread(target=writer_thread_func, args=(results_queue, csv_writer, cancel_event))
            writer_thread.start()

            max_workers = os.cpu_count() or 4
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for file_path in log_files:
                    if cancel_event.is_set():
                        break
                    for scenario in scenarios:
                        if cancel_event.is_set():
                            break
                        futures.append(executor.submit(process_log_file, file_path, scenario, results_queue, cancel_event))

                for future in as_completed(futures):
                    if cancel_event.is_set():
                        break
                    processed_files += 1
                    progress_bar['value'] = processed_files
                    status_label.config(text=f"Processing {processed_files}/{total_files * len(scenarios)} scenarios...")

            results_queue.put(None)
            writer_thread.join()

        if not cancel_event.is_set():
            messagebox.showinfo("Success", f"Analysis complete! Output saved to {output_file}")
        else:
            messagebox.showinfo("Cancelled", "Analysis was cancelled by the user.")
        
    except Exception as e:
        messagebox.showerror("Error", str(e))
    finally:
        start_button.config(state='normal')

def show_splash_screen():
    splash = tk.Toplevel()
    splash.title("Loading Totoro...")
    splash.geometry("400x500+500+200")  # Adjust size and position as needed
    splash.configure(bg="white")
    
    try:
        splash.iconbitmap(resource_path("app.ico"))
    except Exception as e:
        print(f"Error loading icon: {e}")
        
    # ASCII art
    ascii_art = (
"⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⢩⡙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠉⠉⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠇⠀⣿⣿⠸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠁⣰⣿⠸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀⣿⣿⣅⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠁⣸⣿⣿⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⣿⣿⣏⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⠀⢿⣿⠏⢰⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠀⢻⣿⡇⢸⣿⣿⣿⠿⠿⠿⢿⣿⣿⡄⠀⢸⠋⢀⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡧⠄⠈⠋⢗⣈⣤⣴⣶⣾⣿⣷⣶⣶⣤⣅⡀⠀⢈⣛⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠋⢀⣀⣴⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡄⠙⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠋⠀⡀⢊⣨⣉⡙⢿⣿⣿⣿⠿⣿⣿⣿⣿⣿⠟⢉⣭⣍⠲⠈⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣯⣍⣛⣛⣛⡻⠿⠿⠁⠀⠘⡇⣿⡅⣀⡗⢸⣿⣏⣁⡀⠀⠀⢨⣿⣿⠀⣇⢀⣿⠀⠁⠀⠟⣛⣩⣭⣶⣾⣿⣿⣿⣿\n"
"⣿⣿⣟⣛⣛⣛⣛⣛⠿⠟⠀⠀⠀⢸⣷⣄⣉⣁⣴⣿⣿⡿⠿⠒⠑⠚⠛⠿⣽⣷⣌⠉⣡⣤⣀⠀⠀⢛⣛⣛⣛⣛⣛⣻⣿⣿\n"
"⣿⣿⣿⣿⣿⣿⣿⠿⠿⠀⢀⡄⠀⡇⠠⣴⡆⣴⣶⡆⣶⣶⣾⡆⣿⣿⣿⢸⣶⣦⢨⣬⡨⠥⠉⣀⣄⡈⣭⣭⣍⣙⣛⣻⣿⣿\n"
"⣿⣿⣭⣥⣤⣶⣶⡿⠃⢀⣾⡇⠀⠙⢷⣌⣙⠿⢿⡴⣿⣿⣿⡇⣿⣿⣿⡎⣿⡿⠏⢋⣥⣾⣿⣿⣿⣿⣌⠻⣿⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣿⣿⡿⠉⣰⣼⣦⣿⡿⠀⣴⣿⣿⣿⣿⣶⣤⣤⠌⠉⠁⠉⠉⠉⠀⠱⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡌⢿⣿⣿⣿⣿\n"
"⣿⣿⣿⡿⠋⠀⢰⣿⣿⣿⡿⠁⣴⡿⠟⣛⣋⣭⣭⣴⣶⣶⣾⣿⣷⣶⣿⣿⣶⣶⣬⣭⣙⠻⢿⣿⣿⣿⣿⣿⣿⣎⠻⣿⣿⣿\n"
"⣿⣿⣿⠃⠀⣴⣿⠟⡟⠟⠀⣈⣭⣶⣿⣿⣿⣿⣿⣿⣿⠟⠉⠉⠙⠿⣿⣿⣿⣿⣿⠟⡛⠿⣦⣌⠻⣿⣿⣯⢹⣿⣧⠹⣿⣿\n"
"⣿⣿⠁⠀⣰⣿⠃⣰⠇⢀⣼⡿⠛⠁⣐⡈⠙⣿⣿⣿⣅⣤⣶⣷⣶⣤⣼⣿⣿⣿⣁⣨⣤⣄⡈⢻⣷⣌⠻⣿⠸⣿⣿⡇⢹⣿\n"
"⣿⡇⠀⣾⣿⠏⢠⠃⣀⢿⣏⣠⣴⣿⣿⣿⣿⣿⡿⠿⣿⣿⣿⣿⣿⠿⠛⠛⠿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣌⠂⢻⣿⣿⡆⣿\n"
"⡿⠀⣾⣿⡿⠀⠂⣰⡿⢹⠟⠛⠻⢿⣿⣿⠟⢁⣀⣀⣀⣙⣿⣯⣀⣬⣤⣶⣶⣤⣽⣿⡿⠛⢉⠉⠙⢿⣿⣿⣧⢸⣿⣿⣷⢸\n"
"⡇⠘⣾⣿⠃⠀⢰⣿⡵⠃⣠⣴⣤⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣀⣿⣿⣿⠈⣿⣿⣿⡌\n"
"⠁⡄⣿⣿⡧⢀⣿⣿⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⣿⣿⣿⡇\n"
"⠀⢼⣿⡟⠇⣾⣿⣿⡄⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⣿⣿⣿⡇\n"
"⡀⠸⣿⣷⠀⣿⣿⣿⡇⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⣿⣿⡟⢡\n"
"⣧⠀⢿⣿⠀⣿⣿⣿⣇⢻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠇⣿⡿⢃⣿\n"
"⣿⡄⠈⢿⠐⣿⣿⣿⣿⡌⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⢉⡄⣿⠃⣼⣿\n"
"⣿⣿⣄⢀⠐⢿⣿⣿⣿⠿⠄⠙⠻⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠟⠛⣛⣛⠻⢏⣴⣿⠀⢃⣼⣿⣿\n"
"⣿⣿⣿⣰⡀⣿⣿⡟⠁⠀⢀⣤⣾⣷⣆⡙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠃⠀⣰⣾⣿⣿⣿⣦⠸⡟⠐⣸⣿⣿⣿\n"
"⣿⣿⣿⣿⣧⠸⣿⠁⠀⢠⣿⣿⡇⠙⠕⠀⠄⠙⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡟⠀⠀⢰⡟⣹⣿⣿⣿⣿⠂⢣⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣿⣿⣇⠹⠀⠀⣾⡇⠳⡇⠀⠂⢀⠰⣀⢸⣟⢿⣿⣿⣿⣿⣿⣿⣿⠟⠀⠀⠀⠛⠁⣿⡿⣿⣟⠋⢀⣽⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣿⣿⣿⣧⡁⠀⠈⢿⠀⣡⣄⣸⣤⣶⡈⠄⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⣠⣤⣐⣠⠈⠀⢰⡍⢀⣿⣿⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣿⣿⣿⣿⣿⣦⡀⠀⠐⢿⣿⣿⣿⡿⠇⢀⣛⠻⠿⠿⠿⠿⠿⠿⠿⢁⠘⢿⣿⣿⢛⡾⡄⠈⢀⣾⣿⣿⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⣀⣙⣛⣋⣩⣤⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣌⣙⣙⣘⣁⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣿\n"
"⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿\n"
    )

    # Splash screen text
    splash_text = tk.Label(splash, text="Loading Totoro...", font=("Segoe UI", 14, "bold"), bg="white")
    splash_text.pack(pady=(10, 20))

    # Display ASCII art in the splash screen
    ascii_art_label = tk.Label(splash, text=ascii_art, font=("Courier New", 7), bg="white", justify="center")
    ascii_art_label.pack(pady=(20, 10))


    # Keep the splash screen on top
    splash.attributes('-topmost', True)
    splash.update()
    return splash


def main():
    # Optional: Show a splash screen to let user know app is starting
    # This doesn't improve speed, but gives user visual feedback.
    root = tk.Tk()
    root.withdraw()  # Hide main window while loading UI

    splash = show_splash_screen()
    # Simulate some startup delays or do initialization here if needed
    # For demonstration, just sleep a bit:
    time.sleep(1)

    # Now proceed to build the main UI
    root.deiconify()
    splash.destroy()

    root.title("Totoro")
    try:
        root.iconbitmap(resource_path("app.ico"))
    except:
        pass

    # Main title "Totoro"
    title_label = tk.Label(root, text="Totoro", font=("Segoe UI", 24, "bold"))
    title_label.pack(pady=(10, 0))

    # Secondary title "Log Scenario Finder"
    subtitle_label = tk.Label(root, text="The Log Scenario Finder", font=("Segoe UI", 14, "italic"))
    subtitle_label.pack(pady=(0, 10))

    # Description of what the software does
    description_label = tk.Label(
        root,
        text="Totoro will read the logs within a specified directory and\n"
            "search for occurring scenarios defined in your config file.\n"
            "A CSV flagging all found matches will be produced.",
        font=("Segoe UI", 11),
        justify="left"
    )
    description_label.pack(pady=(0, 20))

    frame = tk.Frame(root)
    frame.pack(pady=10)

    tk.Label(frame, text="Log Directory:", font=("Segoe UI", 10)).grid(row=0, column=0, sticky='e', padx=5, pady=5)
    dir_entry = tk.Entry(frame, width=50)
    dir_entry.grid(row=0, column=1, padx=5, pady=5)
    tk.Button(frame, text="Browse", command=lambda: browse_directory(dir_entry)).grid(row=0, column=2, padx=5, pady=5)

    tk.Label(frame, text="Config File:", font=("Segoe UI", 10)).grid(row=1, column=0, sticky='e', padx=5, pady=5)
    config_entry = tk.Entry(frame, width=50)
    config_entry.insert(0, "scenario.json")
    config_entry.grid(row=1, column=1, padx=5, pady=5)
    tk.Button(frame, text="Browse", command=lambda: browse_file(config_entry)).grid(row=1, column=2, padx=5, pady=5)

    progress_bar = ttk.Progressbar(root, length=400, mode='determinate')
    progress_bar.pack(pady=10)

    status_label = tk.Label(root, text="Ready to analyze logs.", font=("Segoe UI", 10))
    status_label.pack(pady=10)

    cancel_event = Event()

    def start_analysis():
        dir_path = dir_entry.get()
        config_path = config_entry.get()

        output_file = datetime.now().strftime("output_%Y-%m-%d_%H-%M-%S.csv")

        if not dir_path or not config_path:
            messagebox.showerror("Error", "Please provide both log directory and config file.")
            return

        if not Path(dir_path).is_dir():
            messagebox.showerror("Error", "The specified log directory does not exist.")
            return

        if not Path(config_path).is_file():
            messagebox.showerror("Error", "The specified config file does not exist.")
            return

        start_button.config(state='disabled')
        progress_bar['value'] = 0
        cancel_event.clear()

        Thread(
            target=analyze_logs,
            args=(dir_path, config_path, output_file, progress_bar, status_label, start_button, cancel_event),
            daemon=True
        ).start()

    def browse_directory(entry_widget):
        selected_dir = filedialog.askdirectory()
        if selected_dir:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, selected_dir)

    def browse_file(entry_widget):
        selected_file = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")])
        if selected_file:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, selected_file)

    def stop_analysis():
        cancel_event.set()
        status_label.config(text="Cancellation requested...")

    start_button = tk.Button(root, text="Start Analysis", command=start_analysis, bg="green", fg="white", font=("Segoe UI", 10, "bold"))
    start_button.pack(pady=5)

    stop_button = tk.Button(root, text="Stop", command=stop_analysis, bg="red", fg="white", font=("Segoe UI", 10, "bold"))
    stop_button.pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    main()
