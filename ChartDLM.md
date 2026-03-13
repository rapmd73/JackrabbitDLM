## Section 1 - Non-Technical Description

This program processes log data to create a visual representation of statistics over time. It reads information from a log file, extracts specific data points related to "Jackrabbit DLM" activity, and then generates a chart. The user can choose to save this chart as either an image file or an interactive HTML file. The chart displays different statistical categories as separate lines, showing their values across various recorded dates and times.

## Section 2 - Technical Analysis

The Python script `DLMstats.py` is designed to read log data from a specified file, parse it to extract statistical information, and then generate a chart visualizing these statistics.

The script begins by importing necessary libraries, including `sys` for command-line arguments, `os`, `time`, `datetime`, `json`, and `plotly` for plotting. It also imports custom modules `DecoratorFunctions` and `FileFunctions`, and appends a custom library path to `sys.path`.

The log file path is defined as `DLMlogs='/home/JackrabbitDLM/Logs/JackrabbitDLM.log'`.

The program checks for command-line arguments. If fewer than one argument is provided (beyond the script name itself), it prints an error message instructing the user to specify either 'I' for image or 'H' for HTML output and then exits. The first command-line argument is converted to lowercase and stored in the `ih` variable. If `ih` is not 'i' or 'h', an error message is printed, and the script exits.

The script then reads the content of the `DLMlogs` file using `FF.ReadFile(DLMlogs)`, removes leading/trailing whitespace with `.strip()`, and splits the content into a list of lines.

A dictionary named `Dates` is initialized to store the parsed statistical data.

The script iterates through each `line` in the `lines` list.
- If the string 'Jackrabbit DLM' is found in the `line`, the loop continues to the next line, effectively skipping header or irrelevant lines.
- For lines that are not skipped, the line is split by spaces into `data`. The first two elements (`data[0]` and `data[1]`) are concatenated to form a datetime string `dt`.
- The `line` is then split by commas into `data` again. The previously constructed `dt` string is removed from the first element of this new `data` list.
- An empty dictionary `stats` is created to hold the statistics for the current log entry.
- The script iterates through the comma-separated parts of the `data`. Each part is split by a colon (`:`) into a key `k` and a value `v`. The key is stripped of whitespace, and the value is converted to an integer after stripping whitespace. This key-value pair is then added to the `stats` dictionary.
- Finally, the `dt` string is used as a key in the `Dates` dictionary, with the corresponding `stats` dictionary as its value.

After processing all log lines, the script prepares to create a chart.
- It determines the output filename `fn`. If `ih` is 'h', `fn` is set to 'DLMstats.html'; otherwise, it's set to 'DLMstats.png'.

The code then builds the data table for the chart:
- The keys (dates) from the `Dates` dictionary are sorted and stored in the `dates` list.
- A set named `fields` is created to collect all unique statistical field names present in the log data. It iterates through the values (statistics dictionaries) in `Dates` and updates the `fields` set with the keys from each statistics dictionary.
- A list named `traces` is initialized to store Plotly scatter traces.
- The script iterates through the sorted unique `fields`. For each `field`:
    - A list `y` is created by iterating through the sorted `dates`. For each `dt`, it retrieves the value of the current `field` from `Dates[dt]`, defaulting to 0 if the field is not present for that date.
    - A `go.Scatter` trace is created with `x` as `dates`, `y` as the collected values, `mode='lines'`, and `name` set to the current `field`. This trace is appended to the `traces` list.

A Plotly figure `fig1` is created using the collected `traces`.

The script then adds a watermark image to the figure:
- If `ih` is 'h', it adds a layout image using a URL (`https://rapmd.net/RAPMDlogo.png`).
- If `ih` is not 'h' (meaning it's 'i'), it adds a layout image using a local file path (`file:///var/www/vhosts/rapmd.net/httpdocs/RAPMDlogo.png`).
In both cases, the image is centered, has an opacity of 0.1, and is scaled.

The y-axis of the figure is updated to have the title 'DLM Calls'.
The layout of the figure is updated with `autosize=True`, a centered title 'JackrabbitDLM Statistics', the `plotly_white` template, and 'Calls' as the legend title.

Finally, the figure is saved:
- If `ih` is 'h', `fig1.write_html(fn)` is called to save the chart as an HTML file.
- If `ih` is not 'h', `fig1.write_image(fn, width=1920/2, height=1024/2)` is called to save the chart as a PNG image with specified dimensions.