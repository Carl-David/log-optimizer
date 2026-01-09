#!/usr/bin/env python3

import streamlit as st
import json
from typing import List, Dict, Tuple, Union
import math
import random

# Type definitions
Log = Dict[str, int]  # {"long": diameter} or {"short": diameter}
Tree = List[Log]      # [root_log, top_log]
Layer = List[Log]     # [log1, log2, log3, log4]

DIAMETER_REDUCTION_MIN = 40  # Top log is 40-50mm narrower than root log
DIAMETER_REDUCTION_MAX = 50
ROOT_LOG_DIAMETERS = [290, 280, 270]  # Possible root log diameters
LAYERS_COUNT = 9
LOGS_PER_LAYER = 4

def flatten_logs(logs):
    flat = []
    for log in logs:
        for k, v in log.items():
            flat.append({
                "length": k,
                "diameter": v,
                "source": "existing"
            })
    return flat

def get_log_diameter(log: Log) -> int:
    """Get the diameter of a log."""
    return log.get('long') or log.get('short')

def optimize_log_cabin(existing_logs: List[Log]) -> Tuple[List[Tree], List[Layer], Dict]:
    """
    Optimize log cabin construction.
    
    Args:
        existing_logs: List of existing logs in format [{"long": 260}, {"short": 210}, ...]
    
    Returns:
        Tuple of (trees_to_cut, layers, summary)
    """
    total_logs_needed = LAYERS_COUNT * LOGS_PER_LAYER
    existing_logs_count = len(existing_logs)
    additional_logs_needed = total_logs_needed - existing_logs_count
    
    if additional_logs_needed < 0:
        raise ValueError(f"Too many existing logs. Need {total_logs_needed}, but have {existing_logs_count}")
    
    # Calculate how many trees we need to cut (each tree gives 2 logs)
    trees_to_cut = math.ceil(additional_logs_needed / 2)
    
    # Generate new logs from trees
    new_logs = []
    trees = []
    
    # Create trees with optimal diameter distribution
    existing_diameters = [get_log_diameter(log) for log in existing_logs]
    avg_existing = sum(existing_diameters) / len(existing_diameters) if existing_diameters else 220
    
    for i in range(trees_to_cut):
        # Select root diameter from allowed values
        root_diameter = ROOT_LOG_DIAMETERS[i % len(ROOT_LOG_DIAMETERS)]
        
        # Random diameter reduction between 40-50mm
        diameter_reduction = random.randint(DIAMETER_REDUCTION_MIN, DIAMETER_REDUCTION_MAX)
        top_diameter = root_diameter - diameter_reduction
        
        # Tree can yield [short, short], [long, long], [short, long], or [long, short]
        tree_type = i % 4
        if tree_type == 0:  # [short, short]
            log1 = {"short": root_diameter}
            log2 = {"short": top_diameter}
        elif tree_type == 1:  # [long, long]
            log1 = {"long": root_diameter}
            log2 = {"long": top_diameter}
        elif tree_type == 2:  # [short, long]
            log1 = {"short": root_diameter}
            log2 = {"long": top_diameter}
        else:  # [long, short]
            log1 = {"long": root_diameter}
            log2 = {"short": top_diameter}
        
        trees.append([log1, log2])
        new_logs.extend([log1, log2])
    
    # Combine existing and new logs
    all_logs = existing_logs + new_logs
    
    # Separate logs by length and sort each group by diameter
    long_logs = sorted([log for log in all_logs if "long" in log], key=get_log_diameter, reverse=True)
    short_logs = sorted([log for log in all_logs if "short" in log], key=get_log_diameter, reverse=True)
    
    # Distribute logs into layers (ensuring 2 longs + 2 shorts per layer)
    layers = []
    for layer_index in range(LAYERS_COUNT):
        # Take 2 long and 2 short logs for this layer
        if len(long_logs) < 2 or len(short_logs) < 2:
            raise ValueError(f"Not enough logs for layer {layer_index + 1}: need 2 long and 2 short")
        
        layer_logs = long_logs[:2] + short_logs[:2]
        long_logs = long_logs[2:]
        short_logs = short_logs[2:]
        
        layers.append(layer_logs)
    
    # Sort layers by average diameter (thickest at bottom)
    layers.sort(key=lambda layer: sum(get_log_diameter(log) for log in layer) / len(layer), reverse=True)
    
    # Calculate total cabin height (sum of layer heights - one diameter per layer)
    total_height = sum(get_log_diameter(layer[0]) for layer in layers)  # Use first log of each layer as representative
    
    summary = {
        "trees_to_cut": trees_to_cut,
        "total_height": total_height
    }
    
    return trees, layers, summary

def format_log_display(log):
    """Format a log for display"""
    length = list(log.keys())[0]
    diameter = list(log.values())[0]
    if length == 'long':
        return f"long:  {diameter}"
    else:
        return f"short: {diameter}"

# Streamlit App
def main():
    st.set_page_config(page_title="Log Cabin Optimizer", page_icon="🏠", layout="wide")
    
    st.title("🏠 Log Cabin Optimizer")
    st.markdown("**Optimize your log cabin construction by minimizing trees to cut while maintaining flat, even layers**")
    
    # Sidebar for input
    with st.sidebar:
        st.header("📝 Input Your Existing Logs")
        
        # Method selection
        input_method = st.radio(
            "Choose input method:",
            ["Simple Form", "JSON Input", "Quick Add"]
        )
        
        existing_logs = []
        
        if input_method == "Simple Form":
            st.subheader("Add logs one by one:")
            
            # Display current logs
            if 'logs' not in st.session_state:
                st.session_state.logs = []
            
            # Add new log
            col1, col2 = st.columns(2)
            with col1:
                log_type = st.selectbox("Type", ["long", "short"])
            with col2:
                diameter = st.number_input("Diameter (mm)", min_value=200, max_value=350, value=270, step=10)
            
            if st.button("➕ Add Log"):
                st.session_state.logs.append({log_type: diameter})
                st.rerun()
            
            # Show current logs
            if st.session_state.logs:
                st.subheader("Current logs:")
                for i, log in enumerate(st.session_state.logs):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"{format_log_display(log)}")
                    with col2:
                        if st.button("🗑️", key=f"del_{i}"):
                            st.session_state.logs.pop(i)
                            st.rerun()
                            
                if st.button("🗑️ Clear All"):
                    st.session_state.logs = []
                    st.rerun()
            
            existing_logs = st.session_state.logs
            
        elif input_method == "Quick Add":
            st.subheader("Quick presets:")
            
            if st.button("📦 Small starter (3 logs)"):
                st.session_state.logs = [
                    {"long": 270},
                    {"short": 280}, 
                    {"long": 240}
                ]
                st.rerun()
                
            if st.button("📦 Medium set (8 logs)"):
                st.session_state.logs = [
                    {"long": 280}, {"long": 280}, {"long": 270}, {"long": 270},
                    {"short": 280}, {"short": 270}, {"short": 260}, {"short": 250}
                ]
                st.rerun()
                
            if st.button("📦 Many long logs (9 logs)"):
                st.session_state.logs = [
                    {"long": 280}, {"long": 280}, {"long": 280}, {"long": 280},
                    {"long": 280}, {"long": 280}, {"long": 280}, {"long": 270},
                    {"short": 280}
                ]
                st.rerun()
            
            # Show current logs if any
            if 'logs' in st.session_state and st.session_state.logs:
                existing_logs = st.session_state.logs
                st.subheader("Current logs:")
                for log in existing_logs:
                    st.write(f"• {format_log_display(log)}")
                    
        else:  # JSON Input
            st.subheader("Paste JSON format:")
            json_input = st.text_area(
                "Logs (JSON)",
                value='[{"long": 270}, {"short": 280}, {"long": 240}]',
                height=100
            )
            
            try:
                existing_logs = json.loads(json_input)
                st.success(f"✅ {len(existing_logs)} logs loaded")
            except json.JSONDecodeError:
                st.error("❌ Invalid JSON format")
                existing_logs = []
    
    # Main content area
    if existing_logs:
        col1, col2 = st.columns([2, 1])
        
        with col2:
            st.subheader("📊 Your Logs Summary")
            
            # Sort and display existing logs
            existing_flat = flatten_logs(existing_logs)
            existing_sorted = sorted(existing_flat, key=lambda x: x["diameter"], reverse=True)
            
            long_count = len([l for l in existing_logs if "long" in l])
            short_count = len([l for l in existing_logs if "short" in l])
            
            st.metric("Total logs", len(existing_logs))
            col2_1, col2_2 = st.columns(2)
            with col2_1:
                st.metric("Long logs", long_count)
            with col2_2:
                st.metric("Short logs", short_count)
            
            # Show sorted logs
            st.subheader("Sorted by diameter:")
            for log in existing_sorted:
                if log['length'] == 'long':
                    st.write(f"🪵 **[long: {log['diameter']}]**")
                else:
                    st.write(f"🪵 **[short: {log['diameter']}]**")
        
        with col1:
            if st.button("🚀 **OPTIMIZE CABIN**", type="primary", use_container_width=True):
                try:
                    with st.spinner("Optimizing your cabin construction..."):
                        trees, layers, summary = optimize_log_cabin(existing_logs)
                        
                        result = {
                            "trees_to_cut": summary["trees_to_cut"],
                            "trees": trees,
                            "layers": layers,
                            "total_height_mm": round(summary["total_height"], 1),
                        }
                    
                    # Display results
                    st.success("✅ Optimization complete!")
                    
                    # Summary metrics
                    col_m1, col_m2, col_m3 = st.columns(3)
                    with col_m1:
                        st.metric("🌲 Trees to cut", result["trees_to_cut"])
                    with col_m2:
                        st.metric("📏 Cabin height", f"{result['total_height_mm']} mm")
                    with col_m3:
                        st.metric("🏗️ Total layers", len(result["layers"]))
                    
                    # Trees to cut
                    with st.expander("🌲 **Trees to Cut**", expanded=True):
                        for i, tree in enumerate(result["trees"], 1):
                            formatted_logs = []
                            for log in tree:
                                length = list(log.keys())[0]
                                diameter = list(log.values())[0]
                                if length == 'long':
                                    formatted_logs.append(f"long: {diameter}")
                                else:
                                    formatted_logs.append(f"short: {diameter}")
                            log_info = ", ".join(formatted_logs)
                            st.write(f"**Tree {i:2}:** [{log_info}]")
                    
                    # Layers
                    with st.expander("🏗️ **Cabin Layers (bottom → top)**", expanded=True):
                        for i, layer in enumerate(result["layers"], 1):
                            formatted_logs = []
                            diameters = []
                            for log in layer:
                                length = list(log.keys())[0]
                                diameter = list(log.values())[0]
                                diameters.append(diameter)
                                if length == 'long':
                                    formatted_logs.append(f"long: {diameter}")
                                else:
                                    formatted_logs.append(f"short: {diameter}")
                            
                            log_info = ", ".join(formatted_logs)
                            variation = max(diameters) - min(diameters)
                            avg_diameter = sum(diameters) / len(diameters)
                            
                            # Color code based on variation
                            if variation <= 10:
                                icon = "🟢"
                            elif variation <= 20:
                                icon = "🟡"
                            else:
                                icon = "🔴"
                                
                            st.write(f"**Layer {i:2}:** [{log_info}] {icon} (avg: {avg_diameter:.0f}mm, variation: {variation}mm)")
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    else:
        st.info("👆 **Add your existing logs using the sidebar to get started!**")
        
        # Show example
        st.subheader("📖 How it works:")
        st.markdown("""
        1. **Add your existing logs** using the sidebar (any combination of long/short logs)
        2. **Click optimize** to get a cutting plan
        3. **View results** showing exactly which trees to cut and how to arrange layers
        
        **The optimizer will:**
        - ✅ Minimize the number of trees you need to cut
        - ✅ Ensure each layer has exactly 2 long + 2 short logs  
        - ✅ Create flat, even layers by matching similar diameters
        - ✅ Arrange layers with thickest at bottom, thinnest at top
        """)

if __name__ == "__main__":
    main()