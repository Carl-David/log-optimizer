#!/usr/bin/env python3

import streamlit as st
import json
from typing import List, Dict, Tuple
import math
import sqlite3

# Type definitions
Log = Dict[str, int]  # {"long": diameter} or {"short": diameter}
Tree = List[Log]      # [root_log, top_log]
Layer = List[Log]     # [log1, log2, log3, log4]

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

def optimize_logs(existing_logs: List[Log], layers_count: int, root_log_diameters: List[int], 
                 long_length: int, short_length: int, diameter_reduction_per_meter: int, shrinkage_percentage: float, bark_thickness: int, belly_groove_reduction: int, minimum_wall_height: int = None) -> Tuple[List[Tree], List[Layer], Dict]:
    """
    Optimize logs.
    
    Args:
        existing_logs: List of existing logs in format [{"long": 260}, {"short": 210}, ...]
        layers_count: Number of layers (courses) to build (None if using minimum_wall_height)
        root_log_diameters: Available root log diameters for new trees
        long_length: Length of long logs in mm
        short_length: Length of short logs in mm
        diameter_reduction_per_meter: Diameter reduction per meter of tree length
        shrinkage_percentage: Percentage of diameter reduction due to wood shrinkage
        bark_thickness: Thickness of bark to subtract from diameter for wall height calculations
        belly_groove_reduction: Wall height reduction due to belly groove, affects all logs except bottom one
        minimum_wall_height: Minimum desired wall height in mm (None if using layers_count)
    
    Returns:
        Tuple of (trees_to_cut, layers, summary)
    """
    # If minimum wall height is specified, calculate required layers_count
    if minimum_wall_height is not None:
        # Estimate average log height after all reductions
        avg_log_diameter = sum(root_log_diameters) / len(root_log_diameters)
        estimated_first_layer_height = max(0, avg_log_diameter - bark_thickness * 2) * (1 - shrinkage_percentage/100)
        estimated_other_layer_height = max(0, avg_log_diameter - bark_thickness * 2 - belly_groove_reduction) * (1 - shrinkage_percentage/100)
        
        # Calculate how many layers we need
        if estimated_other_layer_height <= 0:
            layers_count = 1
        else:
            remaining_height = minimum_wall_height - estimated_first_layer_height
            if remaining_height <= 0:
                layers_count = 1
            else:
                additional_layers = math.ceil(remaining_height / estimated_other_layer_height)
                layers_count = 1 + additional_layers
        
        # Cap at reasonable maximum
        layers_count = min(layers_count, 30)
    
    total_logs_needed = layers_count * 4
    existing_logs_count = len(existing_logs)
    additional_logs_needed = total_logs_needed - existing_logs_count
    
    if additional_logs_needed < 0:
        raise ValueError(f"Too many existing logs. Need {total_logs_needed}, but have {existing_logs_count}")
    
    # Calculate how many trees we need to cut (each tree gives 2 logs)
    trees_to_cut = math.ceil(additional_logs_needed / 2)
    
    # Generate new logs from trees
    new_logs = []
    trees = []
    
    for i in range(trees_to_cut):
        # Select desired middle diameter for the first log from allowed values
        desired_first_log_middle_diameter = root_log_diameters[i % len(root_log_diameters)]
        
        # Tree can yield [short, short], [long, long], [short, long], or [long, short]
        tree_type = i % 4
        if tree_type == 0:  # [short, short]
            # Calculate required root diameter to achieve desired middle diameter for first short log
            # First log middle at short_length/2, so root = desired + taper_to_middle
            required_root_diameter = desired_first_log_middle_diameter + (short_length/2) * (diameter_reduction_per_meter / 1000)
            # First log: middle at short_length/2 (this will be our desired diameter)
            log1_middle_diameter = desired_first_log_middle_diameter
            # Second log: middle at short_length + short_length/2
            log2_middle_diameter = required_root_diameter - (short_length + short_length/2) * (diameter_reduction_per_meter / 1000)
            log1 = {"short": int(log1_middle_diameter)}
            log2 = {"short": int(log2_middle_diameter)}
            tree_dbh = int(required_root_diameter)
        elif tree_type == 1:  # [long, long]
            # Calculate required root diameter to achieve desired middle diameter for first long log
            required_root_diameter = desired_first_log_middle_diameter + (long_length/2) * (diameter_reduction_per_meter / 1000)
            # First log: middle at long_length/2 (this will be our desired diameter)
            log1_middle_diameter = desired_first_log_middle_diameter
            # Second log: middle at long_length + long_length/2
            log2_middle_diameter = required_root_diameter - (long_length + long_length/2) * (diameter_reduction_per_meter / 1000)
            log1 = {"long": int(log1_middle_diameter)}
            log2 = {"long": int(log2_middle_diameter)}
            tree_dbh = int(required_root_diameter)
        elif tree_type == 2:  # [short, long]
            # Calculate required root diameter to achieve desired middle diameter for first short log
            required_root_diameter = desired_first_log_middle_diameter + (short_length/2) * (diameter_reduction_per_meter / 1000)
            # First log: middle at short_length/2 (this will be our desired diameter)
            log1_middle_diameter = desired_first_log_middle_diameter
            # Second log: middle at short_length + long_length/2
            log2_middle_diameter = required_root_diameter - (short_length + long_length/2) * (diameter_reduction_per_meter / 1000)
            log1 = {"short": int(log1_middle_diameter)}
            log2 = {"long": int(log2_middle_diameter)}
            tree_dbh = int(required_root_diameter)
        else:  # [long, short]
            # Calculate required root diameter to achieve desired middle diameter for first long log
            required_root_diameter = desired_first_log_middle_diameter + (long_length/2) * (diameter_reduction_per_meter / 1000)
            # First log: middle at long_length/2 (this will be our desired diameter)
            log1_middle_diameter = desired_first_log_middle_diameter
            # Second log: middle at long_length + short_length/2
            log2_middle_diameter = required_root_diameter - (long_length + short_length/2) * (diameter_reduction_per_meter / 1000)
            log1 = {"long": int(log1_middle_diameter)}
            log2 = {"short": int(log2_middle_diameter)}
            tree_dbh = int(required_root_diameter)
        
        trees.append({"logs": [log1, log2], "dbh": tree_dbh})
        new_logs.extend([log1, log2])
    
    # Combine existing and new logs
    all_logs = existing_logs + new_logs
    
    # Separate logs by length and sort each group by diameter
    long_logs = sorted([log for log in all_logs if "long" in log], key=get_log_diameter, reverse=True)
    short_logs = sorted([log for log in all_logs if "short" in log], key=get_log_diameter, reverse=True)
    
    # Distribute logs into layers (ensuring 2 longs + 2 shorts per layer)
    layers = []
    for layer_index in range(layers_count):
        # Take 2 long and 2 short logs for this layer
        if len(long_logs) < 2 or len(short_logs) < 2:
            raise ValueError(f"Not enough logs for layer {layer_index + 1}: need 2 long and 2 short")
        
        layer_logs = long_logs[:2] + short_logs[:2]
        long_logs = long_logs[2:]
        short_logs = short_logs[2:]
        
        layers.append(layer_logs)
    
    # Sort layers by average diameter (thickest at bottom)
    layers.sort(key=lambda layer: sum(get_log_diameter(log) for log in layer) / len(layer), reverse=True)
    
    # Calculate total cabin height and add accumulated heights with different calculations
    total_height_raw = 0
    total_height_without_bark = 0
    total_height_final = 0
    
    # First pass: calculate total heights for different scenarios
    for i, layer in enumerate(layers):
        # Calculate average diameter for this layer
        avg_diameter = sum(get_log_diameter(log) for log in layer) / len(layer)
        
        # Raw height (just average diameter)
        raw_height = avg_diameter
        total_height_raw += raw_height
        
        # Height without bark
        height_without_bark = max(0, avg_diameter - bark_thickness * 2)
        total_height_without_bark += height_without_bark
        
        # Final height (with proper order: bark removal, then shrinkage, then belly groove)
        height_after_bark_removal = max(0, avg_diameter - bark_thickness * 2)
        height_after_shrinkage = height_after_bark_removal * (1 - shrinkage_percentage/100)
        final_height = height_after_shrinkage
        if i > 0:  # Apply belly groove reduction to all layers except the bottom one
            final_height = max(0, final_height - belly_groove_reduction)
        total_height_final += final_height
    
    # Final height totals already include shrinkage from individual calculations
    
    # Add accumulated heights to each layer with all calculation types
    accumulated_raw = 0
    accumulated_without_bark = 0
    accumulated_final = 0
    
    for i, layer in enumerate(layers):
        # Calculate average diameter for this layer
        avg_diameter = sum(get_log_diameter(log) for log in layer) / len(layer)
        
        # Calculate individual layer heights using proper order
        raw_height = avg_diameter
        height_without_bark = max(0, avg_diameter - bark_thickness * 2)
        
        # For final height: remove bark, apply shrinkage, then belly groove
        height_after_bark_removal = max(0, avg_diameter - bark_thickness * 2)
        height_after_shrinkage = height_after_bark_removal * (1 - shrinkage_percentage/100)
        final_height_after_shrinkage = height_after_shrinkage
        if i > 0:
            final_height_after_shrinkage = max(0, final_height_after_shrinkage - belly_groove_reduction)
        
        # Update accumulated totals
        accumulated_raw += raw_height  # No shrinkage for raw
        accumulated_without_bark += height_without_bark  # No shrinkage for height w/o bark
        accumulated_final += final_height_after_shrinkage
        
        # Add all height data as metadata to the layer
        layer.append({
            "_raw_height": round(raw_height),  # No shrinkage for raw
            "_height_without_bark": round(height_without_bark),  # No shrinkage for height w/o bark
            "_final_height": round(final_height_after_shrinkage),
            "_accumulated_raw": round(accumulated_raw),  # No shrinkage for raw
            "_accumulated_without_bark": round(accumulated_without_bark),  # No shrinkage for height w/o bark
            "_accumulated_final": round(accumulated_final),
            "_accumulated_height": round(accumulated_final)  # Keep for backward compatibility
        })
    
    summary = {
        "trees_to_cut": trees_to_cut,
        "total_height_raw": total_height_raw,
        "total_height_raw_after_shrinkage": round(total_height_raw),  # No shrinkage for raw
        "total_height_without_bark": total_height_without_bark,
        "total_height_without_bark_after_shrinkage": round(total_height_without_bark),  # No shrinkage for height w/o bark
        "total_height_final": total_height_final,
        "total_height_final_after_shrinkage": round(total_height_final),
        "total_height": total_height_final,  # Keep for backward compatibility
        "total_height_after_shrinkage": round(total_height_final)  # Keep for backward compatibility
    }
    
    # If minimum wall height is specified, keep adding layers until requirement is met
    if minimum_wall_height is not None:
        while total_height_final < minimum_wall_height and len(layers) < 30:  # Safety cap
            # Add one more layer with average diameter logs
            avg_diameter = sum(root_log_diameters) / len(root_log_diameters)
            extra_layer = [
                {"long": int(avg_diameter)}, 
                {"long": int(avg_diameter)}, 
                {"short": int(avg_diameter)}, 
                {"short": int(avg_diameter)}
            ]
            layers.append(extra_layer)
            
            # Calculate height contribution of this extra layer for all types
            extra_raw_height = avg_diameter
            extra_height_without_bark = max(0, avg_diameter - bark_thickness * 2)
            # For final height: remove bark, apply shrinkage, then belly groove
            extra_height_after_shrinkage = max(0, avg_diameter - bark_thickness * 2) * (1 - shrinkage_percentage/100)
            extra_final_height = max(0, extra_height_after_shrinkage - belly_groove_reduction)  # Apply belly groove after shrinkage
            
            # Update totals
            total_height_raw += extra_raw_height
            total_height_without_bark += extra_height_without_bark
            total_height_final += extra_final_height
            
            # Recalculate - final height already includes shrinkage from individual calculations
            
            # Update trees_to_cut (need 2 more logs = 1 more tree)
            trees_to_cut += 1
            # Add the tree for the extra logs (consistent with original tree structure)
            log1 = {"long": int(avg_diameter)}
            log2 = {"short": int(avg_diameter)}
            # Calculate DBH properly: add taper from middle of first log back to tree base
            # First log is long, so middle is at long_length/2 from base
            extra_tree_dbh = int(avg_diameter + (long_length/2) * (diameter_reduction_per_meter / 1000))
            trees.append({"logs": [log1, log2], "dbh": extra_tree_dbh})
        
        # Re-sort layers by average diameter after adding extra layers (thickest at bottom)
        layers.sort(key=lambda layer: sum(get_log_diameter(log) for log in layer if isinstance(log, dict) and ('long' in log or 'short' in log)) / len([log for log in layer if isinstance(log, dict) and ('long' in log or 'short' in log)]), reverse=True)
        
        # Recalculate accumulated heights for all layers after adding extra layers
        accumulated_raw = 0
        accumulated_without_bark = 0
        accumulated_final = 0
        
        for i, layer in enumerate(layers):
            # Skip metadata if it exists
            logs_in_layer = [log for log in layer if isinstance(log, dict) and ('long' in log or 'short' in log)]
            if logs_in_layer:
                # Calculate average diameter for this layer
                avg_diameter = sum(get_log_diameter(log) for log in logs_in_layer) / len(logs_in_layer)
                
                # Calculate individual layer heights using average diameter and proper order
                raw_height = avg_diameter
                height_without_bark = max(0, avg_diameter - bark_thickness * 2)
                
                # For final height: remove bark, apply shrinkage, then belly groove
                height_after_bark_removal = max(0, avg_diameter - bark_thickness * 2)
                height_after_shrinkage = height_after_bark_removal * (1 - shrinkage_percentage/100)
                final_height_after_shrinkage = height_after_shrinkage
                if i > 0:
                    final_height_after_shrinkage = max(0, final_height_after_shrinkage - belly_groove_reduction)
                
                # Update accumulated totals
                accumulated_raw += raw_height  # No shrinkage for raw
                accumulated_without_bark += height_without_bark  # No shrinkage for height w/o bark
                accumulated_final += final_height_after_shrinkage
                
                # Remove existing metadata and add updated heights
                layer[:] = logs_in_layer  # Keep only the log dictionaries
                layer.append({
                    "_raw_height": round(raw_height),  # No shrinkage for raw
                    "_height_without_bark": round(height_without_bark),  # No shrinkage for height w/o bark
                    "_final_height": round(final_height_after_shrinkage),
                    "_accumulated_raw": round(accumulated_raw),  # No shrinkage for raw
                    "_accumulated_without_bark": round(accumulated_without_bark),  # No shrinkage for height w/o bark
                    "_accumulated_final": round(accumulated_final),
                    "_accumulated_height": round(accumulated_final)  # Keep for backward compatibility
                })
        
        # Update summary with final values
        summary = {
            "trees_to_cut": trees_to_cut,
            "total_height_raw": total_height_raw,
            "total_height_raw_after_shrinkage": round(total_height_raw),  # No shrinkage for raw
            "total_height_without_bark": total_height_without_bark,
            "total_height_without_bark_after_shrinkage": round(total_height_without_bark),  # No shrinkage for height w/o bark
            "total_height_final": total_height_final,
            "total_height_final_after_shrinkage": round(total_height_final),
            "total_height": total_height_final,  # Keep for backward compatibility
            "total_height_after_shrinkage": round(total_height_final)  # Keep for backward compatibility
        }
    
    return trees, layers, summary

def format_log_display(log):
    """Format a log for display"""
    length = list(log.keys())[0]
    diameter = list(log.values())[0]
    if length == 'long':
        return f"{diameter}L"
    else:
        return f"{diameter}S"

# Database functions
def init_db():
    """Initialize the database and create tables if they don't exist"""
    conn = sqlite3.connect("app.db", check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS existing_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, log_data TEXT)")
    conn.commit()
    return conn

def save_logs_to_db(logs):
    """Save logs list to database"""
    conn = init_db()
    conn.execute("DELETE FROM existing_logs")
    for log in logs:
        log_json = json.dumps(log)
        conn.execute("INSERT INTO existing_logs (log_data) VALUES (?)", (log_json,))
    conn.commit()
    conn.close()

def load_logs_from_db():
    """Load logs from database"""
    conn = init_db()
    cur = conn.execute("SELECT log_data FROM existing_logs")
    rows = cur.fetchall()
    conn.close()
    
    logs = []
    for row in rows:
        try:
            log = json.loads(row[0])
            logs.append(log)
        except json.JSONDecodeError:
            continue
    return logs

def add_log_to_db(log):
    """Add a single log to database"""
    logs = load_logs_from_db()
    logs.append(log)
    save_logs_to_db(logs)

def delete_log_from_db(index):
    """Delete log at specific index"""
    logs = load_logs_from_db()
    if 0 <= index < len(logs):
        logs.pop(index)
        save_logs_to_db(logs)

def clear_logs_in_db():
    """Clear all logs from database"""
    conn = init_db()
    conn.execute("DELETE FROM existing_logs")
    conn.commit()
    conn.close()

# Streamlit App
def main():
    st.set_page_config(page_title="Log Optimizer", page_icon="🏠", layout="wide")
    st.title("Log Optimizer")
    st.markdown("**Helps planning a log cabin by optimizing what trees to cut, how to cut them, and how to arrange each course!**")

    # Initialize database
    init_db()
    
    # Sidebar for input
    with st.sidebar:
        st.header("Configuration")
        
        # Choose between courses or minimum height
        optimization_method = st.radio(
            "Optimization method:",
            ["Minimum wall height", "Number of courses"]
        )
        
        if optimization_method == "Minimum wall height":
            minimum_wall_height = st.number_input("Minimum wall height (mm)", min_value=500, max_value=5000, value=1740, step=50)
            layers_count = None
        else:
            layers_count = st.number_input("Number of courses", min_value=1, max_value=20, value=9, step=1)
            minimum_wall_height = None
        
        st.subheader("Log dimensions")
        long_length = st.number_input(
            "Long log length (mm)", 
            min_value=3000, max_value=8000, value=5150, step=50,
            help="Length of long logs in millimeters"
        )
        short_length = st.number_input(
            "Short log length (mm)", 
            min_value=2000, max_value=6000, value=4050, step=50,
            help="Length of short logs in millimeters"
        )
        diameter_reduction_per_meter = st.number_input(
            "Diameter reduction per meter (mm/m)", 
            min_value=5, max_value=20, value=10, step=1,
            help="How many millimeters the tree diameter reduces per meter of length"
        )
        shrinkage_percentage = st.number_input(
            "Wood shrinkage (%)", 
            min_value=0, max_value=20, value=6, step=1,
            help="Percentage of diameter reduction due to wood shrinkage after drying"
        )
        bark_thickness = st.number_input(
            "Bark thickness (mm)", 
            min_value=0, max_value=25, value=6, step=1,
            help="Thickness of bark on one side at root log center. Will be doubled in calculations (both sides) to subtract from diameter for wall height calculations"
        )
        belly_groove_reduction = st.number_input(
            "Belly groove reduction (mm)", 
            min_value=0, max_value=50, value=25, step=1,
            help="Wall height reduction due to cutting of the belly groove, affects all logs except the bottom one"
        )
        
        # Root log diameters input
        st.subheader("Available tree sizes")
        diameter_input = st.text_input(
            "Root log middle diameters with bark (in mm, comma-separated)",
            value="287",
            help="Enter the desired diameters with bark at the middle of the first (root) log cut from each tree, comma-separated"
        )
        
        try:
            root_log_diameters = [int(d.strip()) for d in diameter_input.split(',') if d.strip()]
            if not root_log_diameters:
                st.error("❌ Please enter at least one diameter")
                root_log_diameters = [290, 280, 270]  # fallback
            elif any(d < 100 or d > 500 for d in root_log_diameters):
                st.warning("⚠️ Some diameters seem unusual (should be 100-500mm)")
        except ValueError:
            st.error("❌ Invalid format. Use numbers separated by commas (e.g., 290, 280, 270)")
            root_log_diameters = [290, 280, 270]  # fallback
        
        st.divider()
        
        st.header("Add Existing Logs")
        st.info("💡 Diameters should be measured at the middle of the root logs with bark")
        
        # Method selection
        input_method = st.radio(
            "Choose input method:",
            ["Simple Form", "JSON Input"]
        )
        
        existing_logs = []
        
        if input_method == "Simple Form":
            st.subheader("Add logs one by one:")
            
            # Load current logs from database
            current_logs = load_logs_from_db()
            
            # Add new log
            col1, col2 = st.columns(2)
            with col1:
                diameter = st.number_input("Diameter (mm)", min_value=100, max_value=400, value=287, step=10)
            with col2:
                log_type = st.radio("Type", ["Long", "Short"])
            
            if st.button("➕ Add Log"):
                add_log_to_db({log_type.lower(): diameter})
                st.rerun()
            
            # Show current logs
            if current_logs:
                st.subheader("Current logs:")
                for i, log in enumerate(current_logs):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"{format_log_display(log)}")
                    with col2:
                        if st.button("🗑️", key=f"del_{i}"):
                            delete_log_from_db(i)
                            st.rerun()
                            
                if st.button("🗑️ Clear All"):
                    clear_logs_in_db()
                    st.rerun()
            
            existing_logs = current_logs
            
        else:  # JSON Input
            st.subheader("Paste JSON format:")
            
            # Load current logs to populate the text area
            current_logs = load_logs_from_db()
            default_value = json.dumps(current_logs) if current_logs else '[{"long": 287}, {"short": 287}, {"long": 287}, {"short": 287}]'
            
            json_input = st.text_area(
                "Logs (JSON)",
                value=default_value,
                height=100
            )
            
            try:
                parsed_logs = json.loads(json_input)
                existing_logs = parsed_logs
                st.success(f"✅ {len(existing_logs)} logs loaded")
                
                # Auto-save to database when JSON changes
                if json_input != default_value:
                    save_logs_to_db(existing_logs)
                    
            except json.JSONDecodeError:
                st.error("❌ Invalid JSON format")
                existing_logs = current_logs  # Fall back to current logs
    
    # Initialize result variable for tracking optimization results
    result = None
    
    # Main content area
    col1, col2 = st.columns([2, 1], gap="medium")
    
    with col1:
        # Always show both buttons side by side
        col_btn1, col_btn2 = st.columns(2, gap="small")
        with col_btn1:
            optimize_from_scratch = st.button("🚀 **OPTIMIZE FROM SCRATCH**", type="primary", use_container_width=True)
        with col_btn2:
            optimize_with_existing = st.button("🔧 **OPTIMIZE WITH EXISTING LOGS**", type="primary", use_container_width=True, disabled=not existing_logs)
        
        if optimize_from_scratch or optimize_with_existing:
            try:
                with st.spinner("Optimizing your logs..."):
                    # Determine which logs to use based on button pressed
                    logs_to_use = [] if optimize_from_scratch else existing_logs
                    
                    trees, layers, summary = optimize_logs(
                        logs_to_use, layers_count, root_log_diameters,
                        long_length, short_length, diameter_reduction_per_meter, shrinkage_percentage, bark_thickness, belly_groove_reduction, minimum_wall_height
                    )
                    
                    result = {
                        "trees_to_cut": summary["trees_to_cut"],
                        "trees": trees,
                        "layers": layers,
                        "total_height_mm": summary["total_height_final"],
                        "total_height_after_shrinkage_mm": summary["total_height_final_after_shrinkage"],
                        "total_height_raw_after_shrinkage_mm": summary["total_height_raw_after_shrinkage"],
                        "total_height_without_bark_after_shrinkage_mm": summary["total_height_without_bark_after_shrinkage"],
                    }
                    
                    # Store result in session state for access by existing logs display
                    st.session_state.optimization_result = result
                
                # Display results
                mode_text = "from scratch" if optimize_from_scratch else "using existing logs"
                st.success(f"✅ Optimization complete ({mode_text})!")
                
                # Summary metrics
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.metric("🌲 Trees to cut", result["trees_to_cut"])
                with col_m2:
                    st.metric("🏗️ Total courses", len(result["layers"]))
                
                 # Summary metrics
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    st.metric("📏 Raw height (no reductions)", f"{result.get('total_height_raw_after_shrinkage_mm', 0)} mm")
                with col_m2:
                    st.metric("📏 No bark height", f"{result.get('total_height_without_bark_after_shrinkage_mm', 0)} mm")
                with col_m3:
                    st.metric("📏 Final height (dried & belly grooved)", f"{result['total_height_after_shrinkage_mm']} mm")
                
                # Trees to cut
                with st.expander("🌲 **Trees to Cut**", expanded=True):
                    for i, tree in enumerate(result["trees"], 1):
                        formatted_logs = []
                        logs = tree["logs"] if isinstance(tree, dict) and "logs" in tree else tree
                        for log in logs:
                            length = list(log.keys())[0]
                            diameter = list(log.values())[0]
                            if length == 'long':
                                formatted_logs.append(f"{diameter}L")
                            else:
                                formatted_logs.append(f"{diameter}S")
                        log_info = ", ".join(formatted_logs)
                        
                        # Add DBH if available
                        dbh_info = ""
                        if isinstance(tree, dict) and "dbh" in tree:
                            dbh_info = f" - (*{tree['dbh']} DBH*)"
                        
                        st.write(f"**Tree {i:2}:** [{log_info}]{dbh_info}")
                
                # Layers
                with st.expander("🏗️ **Courses (bottom → top)**", expanded=True):
                    for i, layer in enumerate(result["layers"], 1):
                        formatted_logs = []
                        diameters = []
                        height_data = {}
                        
                        for log in layer:
                            if isinstance(log, dict) and any(k.startswith('_') for k in log.keys()):
                                height_data = log
                            else:
                                # Check if log is from existing_logs (before optimization)
                                is_existing = log in existing_logs
                                
                                length = list(log.keys())[0]
                                diameter = list(log.values())[0]
                                diameters.append(diameter)
                                
                                if length == 'long':
                                    if is_existing:
                                        formatted_logs.append(f"*{diameter}L*")
                                    else:
                                        formatted_logs.append(f"{diameter}L")
                                else:
                                    if is_existing:
                                        formatted_logs.append(f"*{diameter}S*")
                                    else:
                                        formatted_logs.append(f"{diameter}S")
                        
                        log_info = ", ".join(formatted_logs)
                        
                        # Safety check to prevent max() on empty list
                        if diameters:
                            variation = max(diameters) - min(diameters)
                            avg_diameter = sum(diameters) / len(diameters)
                        else:
                            variation = 0
                            avg_diameter = 0
                        
                        # Color code based on variation
                        if variation <= 10:
                            icon = "🟢"
                        elif variation <= 20:
                            icon = "🟡"
                        else:
                            icon = "🔴"
                        
                        # Build height info string - show both individual course height and accumulated total
                        height_info = ""
                        if height_data:
                            individual_heights = f"Heights: R{height_data.get('_raw_height', 0)}, NB{height_data.get('_height_without_bark', 0)}, F{height_data.get('_final_height', 0)}"
                            # Make entire "Total:" line bold if this is the last course
                            if i == len(result["layers"]):
                                accumulated_heights = f"**Total: R{height_data.get('_accumulated_raw', 0)}, NB{height_data.get('_accumulated_without_bark', 0)}, F{height_data.get('_accumulated_final', 0)}**"
                            else:
                                accumulated_heights = f"Total: R{height_data.get('_accumulated_raw', 0)}, NB{height_data.get('_accumulated_without_bark', 0)}, F{height_data.get('_accumulated_final', 0)}"
                            height_info = f" | {individual_heights} | {accumulated_heights}"
                        
                        # Format variation with extra space for single digits to improve alignment
                        variation_text = f"Δ: {variation} mm\xa0\xa0" if variation < 10 else f"Δ: {variation} mm"
                        course_text = f"**Course {i:2}:**\xa0\xa0\xa0" if i < 10 else f"**Course {i:2}:** "
                        st.write(f"{course_text}[{log_info}] {icon} (ø: {avg_diameter:.0f} mm, {variation_text}{height_info})")
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

        # Show example/instructions
        if not existing_logs:
            st.subheader("How it works:")
            st.markdown("""
            1. **Add your existing logs** using the sidebar (any combination of long/short logs)
            2. **Or click "Plan from Scratch"** to get a complete cutting plan  
            3. **View results** showing exactly which trees to cut and how to arrange courses
            
            **The optimizer will:**
            - ✅ Minimize the number of trees you need to cut
            - ✅ Ensure each course has exactly 2 long + 2 short logs  
            - ✅ Create flat, even courses by matching similar diameters
            - ✅ Arrange courses with thickest at bottom, thinnest at top
            """)
    
    with col2:
        st.subheader("Existing Logs")
        
        if existing_logs:
            # Sort and display existing logs
            existing_flat = flatten_logs(existing_logs)
            existing_sorted = sorted(existing_flat, key=lambda x: x["diameter"], reverse=False)
            
            long_count = len([l for l in existing_logs if "long" in l])
            short_count = len([l for l in existing_logs if "short" in l])
            avg_diameter = sum(existing_flat[i]["diameter"] for i in range(len(existing_flat))) / len(existing_flat) if existing_flat else 0
            
            col2_1, col2_2 = st.columns(2)
            with col2_1:
                st.metric("Total logs", f"{len(existing_logs)}")
            with col2_2:
                st.metric("Average diameter", f"{avg_diameter:.0f} mm")

            col2_1, col2_2 = st.columns(2)
            with col2_1:
                st.metric("Long logs", long_count)
            with col2_2:
                st.metric("Short logs", short_count)
            
            # Show sorted logs
            st.subheader("Sorted by diameter:")
            
            # Check if we have optimization results to determine usage
            if hasattr(st.session_state, 'optimization_result') and st.session_state.optimization_result:
                # Collect all logs used in layers
                used_logs = []
                for layer in st.session_state.optimization_result["layers"]:
                    for log in layer:
                        if isinstance(log, dict) and not any(k.startswith('_') for k in log.keys()):
                            used_logs.append(log)
                
                # Display existing logs with usage status
                for log_flat in existing_sorted:
                    # Reconstruct original log format for comparison
                    original_log = {log_flat['length']: log_flat['diameter']}
                    is_used = original_log in used_logs
                    
                    usage_text = "" if is_used else " (not used)"
                    if log_flat['length'] == 'long':
                        st.write(f"🪵 {log_flat['diameter']}L{usage_text}")
                    else:
                        st.write(f"🪵 {log_flat['diameter']}S{usage_text}")
            else:
                # No optimization results yet, show logs without usage info
                for log in existing_sorted:
                    if log['length'] == 'long':
                        st.write(f"🪵 {log['diameter']}L")
                    else:
                        st.write(f"🪵 {log['diameter']}S")
        else:
            st.info("No existing logs yet")
            st.write("👈 Add logs using the sidebar or optimize with 0 existing logs")

if __name__ == "__main__":
    main()