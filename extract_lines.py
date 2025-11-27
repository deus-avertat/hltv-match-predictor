# extract_lines.py
start_line = 1289044
end_line = 1412560
input_file = "hltv_data.json"
output_file = "extracted_data.json"

with open(input_file, 'r', encoding='utf-8') as infile, open(output_file, 'w', encoding='utf-8') as outfile:
    for i, line in enumerate(infile, 1):  # Start counting from line 1
        if start_line <= i <= end_line:
            outfile.write(line)
        elif i > end_line:
            break  # Stop reading after the last line