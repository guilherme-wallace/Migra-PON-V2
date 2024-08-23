import json
PON_ANTIGA = "0/1/0"
gPON = "/".join(PON_ANTIGA.split("/")[2:3])

# Definindo o nome dos arquivos de entrada e saída
input_file = 'onu_huawei_desc.txt'
output_file_json = 'onu_huawei_desc.json'
output_file_txt = 'ONTdelete.txt'

# Lista para armazenar os dados extraídos
onu_data = []

# Função para processar cada linha do arquivo
def process_line(line):
    # Divide a linha por espaços, mantendo as colunas desejadas
    parts = line.split()
    if len(parts) >= 6:
        onu_entry = {
            "ID": parts[0],
            "SN": parts[1],
            "SINAL": parts[4],
            "DESC": " ".join(parts[5:])
        }
        onu_data.append(onu_entry)

# Lê o arquivo linha por linha e processa cada uma
with open(input_file, 'r') as file:
    for line in file:
        if line.strip():  # Ignora linhas em branco
            process_line(line)

# Salva os dados extraídos em um arquivo JSON
with open(output_file_json, 'w') as json_file:
    json.dump(onu_data, json_file, indent=4)

print(f'Dados ONUs salvos em {output_file_json}')

# Cria o arquivo delete_commands.txt com os comandos "ont delete {ID}"
with open(output_file_txt, 'w') as txt_file:
    for onu in onu_data:
        txt_file.write(f'ont delete {gPON} {onu["ID"]}\n')

print(f'Comandos de exclusão salvos em {output_file_txt}')
