#!/bin/bash

# Enhanced status line with emojis and separators
# Preserves all existing functionality from the original command

# Parse JSON input
input=$(cat)
cwd=$(echo "$input" | jq -r '.workspace.current_dir')
model=$(echo "$input" | jq -r '.model.display_name')

# Get current time
time=$(date +%H:%M)

# Change to working directory and get git info
cd "$cwd" 2>/dev/null && branch=$(git symbolic-ref --short HEAD 2>/dev/null) || branch=""

# Git status logic (preserved from original)
if [ -d ".git" ]; then
    diff_stat=$(git diff --shortstat 2>/dev/null)
    if [ -n "$diff_stat" ]; then
        files=$(echo "$diff_stat" | awk '{print $1}')
        insertions=$(echo "$diff_stat" | awk '{for(i=1;i<=NF;i++) if($i ~ /insertion/) print $(i-1)}')
        deletions=$(echo "$diff_stat" | awk '{for(i=1;i<=NF;i++) if($i ~ /deletion/) print $(i-1)}')
        
        [ -n "$insertions" ] && ins="+$insertions" || ins=""
        [ -n "$deletions" ] && del="-$deletions" || del=""
        [ "$files" = "1" ] && file_prefix="" || file_prefix="${files}f "
        
        git_info="${file_prefix}${ins} ${del}"
        git_info=$(echo "$git_info" | sed 's/  */ /g' | sed 's/ $//')
        [ -z "$git_info" ] && git_info="clean"
    else
        git_info="clean"
    fi
else
    git_info="no-git"
fi

# Build enhanced status line with emojis and separators
printf "🕐 \033[33m%s\033[0m | 🤖 \033[35m%s\033[0m" "$time" "$model"

# Add branch info if available
[ -n "$branch" ] && printf " | 🌿 \033[32m[%s]\033[0m" "$branch"

# Add git status with 📊 emoji
printf " | 📊 \033[37m[\033[0m"

# Preserve original color coding for git status
if [ "$git_info" != "clean" ] && [ "$git_info" != "no-git" ]; then
    # Handle file count
    if echo "$git_info" | grep -q 'f '; then
        printf "\033[36m%sf\033[0m " "$(echo "$git_info" | awk '{print $1}' | sed 's/f//')"
        git_info=$(echo "$git_info" | cut -d' ' -f2-)
    fi
    
    # Handle insertions
    if echo "$git_info" | grep -q '+'; then
        printf "\033[32m%s\033[0m" "$(echo "$git_info" | awk '{print $1}')"
        git_info=$(echo "$git_info" | cut -d' ' -f2-)
    fi
    
    # Handle deletions
    if echo "$git_info" | grep -q '-'; then
        printf " \033[31m%s\033[0m" "$(echo "$git_info" | awk '{print $1}')"
    fi
else
    printf "%s" "$git_info"
fi

printf "\033[37m]\033[0m ▶"