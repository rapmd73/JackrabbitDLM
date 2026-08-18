#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChartDLM - Log Statistics Visualizer

Parses JackrabbitDLM.log and generates interactive or static charts
of server statistics over time.

Usage:
    python3 chart_dlm.py [I|H]
    
    I = PNG image output
    H = Interactive HTML output

Requires: plotly

See also:
    - https://en.wikipedia.org/wiki/Data_visualization
    - https://en.wikipedia.org/wiki/Time_series
"""

import sys
import os
import math
import json

try:
    import plotly.graph_objects as go
except ImportError:
    print("plotly required: pip install plotly")
    sys.exit(1)

BASE_DIR = os.environ.get("JACKRABBIT_BASE", "/home/JackrabbitDLM")
LOG_FILE = os.path.join(BASE_DIR, "Logs", "JackrabbitDLM.log")


def parse_log(log_path):
    """Parse JackrabbitDLM.log into {datetime: {stat: value}} dict."""
    dates = {}

    if not os.path.exists(log_path):
        print(f"Log file not found: {log_path}")
        return dates

    with open(log_path, 'r') as f:
        lines = f.read().strip().split('\n')

    for line in lines:
        # Skip non-statistics lines
        skip_keywords = ['Jackrabbit DLM', 'Another program is using this port',
                         'DLMerror', 'Errno', 'Error']
        if any(kw in line for kw in skip_keywords):
            continue

        parts = line.split(' ')
        if len(parts) < 2:
            continue
        dt = parts[0] + ' ' + parts[1]

        stats = {}
        segments = line.split(',')
        segments[0] = segments[0].replace(dt, '')

        for seg in segments:
            if ':' not in seg:
                continue
            k, v = seg.split(':', 1)
            k = k.strip()
            try:
                v = int(v.strip())
            except ValueError:
                try:
                    v = float(v.strip())
                except ValueError:
                    continue
            stats[k] = v

        if stats:
            dates[dt] = stats

    return dates


def chart(output_type='h'):
    """Generate chart from log data."""
    dates = parse_log(LOG_FILE)
    if not dates:
        print("No data to chart.")
        return

    sorted_dates = sorted(dates.keys())
    fields = set()
    for v in dates.values():
        fields.update(v.keys())

    traces = []
    for field in sorted(fields):
        y_raw = [dates[dt].get(field, 0) for dt in sorted_dates]
        y = y_raw if output_type == 'h' else [math.log(v + 1) for v in y_raw]
        traces.append(go.Scatter(x=sorted_dates, y=y, mode='lines', name=field))

    fig = go.Figure(traces)
    fig.update_yaxes(title_text='DLM Calls')
    fig.update_layout(
        autosize=True,
        title={"text": "JackrabbitDLM Statistics", "x": 0.5, "xanchor": "center"},
        template='plotly_white',
        legend_title='Calls'
    )

    if output_type == 'h':
        fn = 'DLMstats.html'
        fig.write_html(fn)
    else:
        fn = 'DLMstats.png'
        fig.write_image(fn, width=960, height=512)

    print(f"Chart saved: {fn}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 chart_dlm.py [I|H]")
        sys.exit(1)

    mode = sys.argv[1].lower()
    if mode not in ('i', 'h'):
        print("Specify I (image) or H (html)")
        sys.exit(1)

    chart(mode)
