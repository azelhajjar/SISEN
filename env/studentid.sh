#!/bin/bash
# Author: Dr Ayman El hajjar
# Student ID Prompt Customization Script
# Sets or resets the terminal prompt to display student ID
# Usage: ./studentid.sh (to set ID) | ./studentid.sh --reset (to restore default)

r="\033[1;31m"
b="\033[1;34m"
w="\033[0m"

BASHRC="$HOME/.bashrc"
BACKUP="$HOME/.bashrc.bak"
MARKER="# --- STUDENT_ID_PROMPT ---"

# Show usage message first
echo -e "${b}To set your Student ID, run: ./studentid.sh and enter your Student ID when prompted.${w}"
echo -e "${b}To reset the prompt and remove any customisations, run:   ./studentid.sh --reset${w}"
echo ""

# Reset mode
if [[ "$1" == "--reset" ]]; then
    echo -e "${b}Restoring original prompt...${w}"
    if [[ -f "$BACKUP" ]]; then
        cp "$BACKUP" "$BASHRC"
        echo -e "${b}Prompt reset to default. Please restart the terminal.${w}"
    else
        echo -e "${r}Backup not found. Cannot restore original .bashrc.${w}"
    fi
    exit 0
fi

# Prompt for student ID
echo -e "${r}Please enter your Student ID:${w}"
read STUDENT_ID

# Backup once
if [[ ! -f "$BACKUP" ]]; then
    cp "$BASHRC" "$BACKUP"
fi

# Remove old student ID prompt (if re-run)
sed -i "/$MARKER/d" "$BASHRC"

# Append new prompt
echo "
$MARKER
export PS1=\"Student ID: $STUDENT_ID | \u@\h:\w\$ \"
" >> "$BASHRC"

echo -e "${b}Student ID prompt added. Please restart the terminal to see the change.${w}"
