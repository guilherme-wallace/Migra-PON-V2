import paramiko
import time
import re
import os
import json
from dadosConexaoOLTs import *

# Mapeamento das OLTs e seus IPs
OLT_IPS = {
    "OLT-SEA01": ip_SEA01,
    "OLT-SEA03": ip_SEA03,
    "OLT-VTA01": ip_VTA01,
    "OLT-VTA02": ip_VTA02,
    "OLT-VVA01": ip_VVA01,
    "OLT-VVA03": ip_VVA03,
    "OLT-CCA01": ip_CCA01,
}
#------------------------------------------------------------------------------------------------------------
# Seleciona a OLT a ser usada
USE_OLT = "OLT-SEA01"  # Certifique-se de que o IP e as credenciais estão corretos
PON_ANTIGA = "0/1/0"
#PON_NOVA = "0/1/0"

# VLAN do serviço
VLAN_IN = 1904

# VLAN de saída para ONU
VLAN_OUT = 1904

# Inicializa variáveis
PON_ZERA = "0"
ONU_ID = 0
ONT_SRV_PROF = 1904
ONT_LIN_PROF = 1904
GEM_PORT = 126
#------------------------------------------------------------------------------------------------------------


# Arquivo contendo a lista de ONUs
ONU_FILE = 'onu_huawei.txt'

# Arquivo contendo as descrições das ONUs
ONU_FILE_DESC = 'onu_huawei_desc.txt'

LISTA_ONUS = 'lista_onus_hw.txt'
LISTA_SRV = 'lista_onus_hw_srv.txt'

hostname = OLT_IPS.get(USE_OLT)

# Dados de acesso SSH
username = user
password = user_password

# Comandos para a OLT
commandsSummary = [
    "enable",
    "config",
    f"display ont info summary {PON_ANTIGA} | no-more"
]

def ssh_connect_and_executeSummary(hostname, username, password, commandsSummary, delay=0.2, timeout=6, max_loops=10):
    # Cria um cliente SSH
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # Conecta ao host via SSH com timeout
        client.connect(hostname, username=username, password=password, timeout=timeout)

        # Cria um shell interativo
        ssh_shell = client.invoke_shell()

        full_output = ""

        # Executa os comandos no shell
        for command in commandsSummary:
            ssh_shell.send(command + '\n')
            time.sleep(delay)  # Aguarda um tempo para o comando ser processado

            # Aguarda até que o comando seja processado
            output = ""
            loops = 0
            while loops < max_loops:
                if ssh_shell.recv_ready():
                    chunk = ssh_shell.recv(4096).decode('utf-8')
                    output += chunk

                    # Verifica se a resposta contém a solicitação de Enter
                    if "{ <cr>||<K> }" in chunk:
                        ssh_shell.send('\n')  # Envia Enter para continuar
                        time.sleep(delay)  # Aguarda após o Enter

                    # Verifica se o prompt final foi alcançado
                    if "SEA01-OLT-01-ITVP(config)#" in chunk or "SEA01-OLT-01-ITVP#" in chunk:
                        break  # Sai do loop se o prompt foi alcançado

                else:
                    time.sleep(0.5)  # Aguarda um pouco antes de verificar novamente

                loops += 1

            full_output += output  # Armazena a saída completa para processamento posterior

        # Filtra as linhas desejadas usando expressão regular
        onu_huawei_desc = re.findall(r'^\s*\d+\s+[A-F0-9]+\s+\S+\s+.*$', full_output, re.MULTILINE)

        # Salva as linhas filtradas em um arquivo
        with open('onu_huawei_desc.txt', 'w') as file:
            file.write('\n'.join(onu_huawei_desc))

        print("As linhas filtradas foram salvas em 'onu_huawei_desc.txt'.")

    except Exception as e:
        print(f"Erro ao conectar ou executar comandos: {e}")
    finally:
        # Fecha a conexão SSH
        client.close()

# Executa a função
ssh_connect_and_executeSummary(hostname, username, password, commandsSummary, delay=0.2, timeout=6, max_loops=10)

# Limpa os arquivos de saída
open(LISTA_ONUS, 'w').close()
open(LISTA_SRV, 'w').close()

# Lê o arquivo de ONUs e armazena o número total de ONUs
with open(ONU_FILE, 'r') as f:
    onu_lines = f.readlines()

total_onus = [line.split()[3] for line in onu_lines if "Ont SN" in line]

# Processa cada ONU
contServiceport = 0
for ONU_SN in total_onus:
    # Busca a linha que contém o ONU_SN
    sn_index = next(i for i, line in enumerate(onu_lines) if ONU_SN in line)
    
    # Procura pela linha contendo "F/S/P" nas linhas anteriores
    porta_pon_line = None
    for i in range(sn_index, -1, -1):
        if "F/S/P" in onu_lines[i]:
            porta_pon_line = onu_lines[i]
            break
    
    if porta_pon_line:
        porta_pon = porta_pon_line.split()[2] if len(porta_pon_line.split()) >= 3 else None
        if porta_pon and '/' in porta_pon:
            pon_id = porta_pon.split('/')[2]
        else:
            print(f"Erro: Porta PON inválida para ONU {ONU_SN}")
            print(f"Conteúdo da linha: {porta_pon_line.strip()}")
            continue
    else:
        print(f"Erro: Linha da Porta PON não encontrada para ONU {ONU_SN}")
        continue

    modelo_line = next((line for line in onu_lines if ONU_SN in line), None)
    modelo = modelo_line.split()[3] if modelo_line and len(modelo_line.split()) >= 4 else None

    if modelo in ["SH1020W", "FD511G-X", "HG9"]:
        onu_oper = "ROUTER"
    else:
        onu_oper = "BRIDGE"

    with open(ONU_FILE_DESC, 'r') as f:
        onu_desc_lines = f.readlines()
    
    onu_desc = next((line.split()[5] for line in onu_desc_lines if ONU_SN[8:16] in line), ONU_SN)

    with open(LISTA_ONUS, 'a') as lista_onus_file:
        lista_onus_file.write(f'ont add {pon_id} {ONU_ID} sn-auth {ONU_SN} omci ont-lineprofile-id {ONT_LIN_PROF} ont-srvprofile-id {ONT_SRV_PROF} desc "{onu_desc}"\n\n')
        
        if onu_oper == "ROUTER":
            for i in range(1, 5):
                lista_onus_file.write(f'ont port route {pon_id} {ONU_ID} eth {i} enable\n\n')
        else:
            lista_onus_file.write(f'ont port native-vlan {pon_id} {ONU_ID} eth 1 vlan {VLAN_OUT} priority 0\n\n')

    with open(LISTA_SRV, 'a') as lista_srv_file:
        contServiceport = contServiceport + 1
        if onu_oper == "ROUTER":
            lista_srv_file.write(f'service-port vlan {VLAN_OUT} gpon {porta_pon} ont {ONU_ID} gemport {GEM_PORT} multi-service user-vlan untagged tag-transform default\n\n')
        else:
            lista_srv_file.write(f'service-port vlan {VLAN_IN} gpon {porta_pon} ont {ONU_ID} gemport {GEM_PORT} multi-service user-vlan {VLAN_OUT} tag-transform translate\n\n')

    ONU_ID += 1

# Exibe o conteúdo dos arquivos gerados
with open(LISTA_ONUS, 'r') as lista_onus_file:
    print(lista_onus_file.read())

print()

with open(LISTA_SRV, 'r') as lista_srv_file:
    print(lista_srv_file.read())

def deleta_onu():    
    # Definindo o nome dos arquivos de entrada e saída
    onu_huawei_descJSON = 'onu_huawei_desc.json'
    ONTdeleteTXT = 'ONTdelete.txt'
    currentONT = 'currentONT.txt'

    # Definindo a interface GPON com base em PON_ANTIGA
    interfaceGPON = "/".join(PON_ANTIGA.split("/")[0:2])
    gPON = "/".join(PON_ANTIGA.split("/")[2:3])

    # Lista para armazenar os dados extraídos
    listaONU = []

    # Função para processar cada linha do arquivo
    def process_lineONUsJSON(line):
        # Divide a linha por espaços, mantendo as colunas desejadas
        parts = line.split()
        if len(parts) >= 6:
            onu_entry = {
                "ID": parts[0],
                "SN": parts[1],
                "SINAL": parts[4],
                "DESC": " ".join(parts[5:])
            }
            listaONU.append(onu_entry)

    # Lê o arquivo linha por linha e processa cada uma
    with open(ONU_FILE_DESC, 'r') as file:
        for line in file:
            if line.strip():  # Ignora linhas em branco
                process_lineONUsJSON(line)

    # Salva os dados extraídos em um arquivo JSON
    with open(onu_huawei_descJSON, 'w') as json_file:
        json.dump(listaONU, json_file, indent=4)

    print(f'Dados ONUs salvos em {onu_huawei_descJSON}')

    # Cria o arquivo delete_commands.txt com os comandos "ont delete {ID}"
    with open(ONTdeleteTXT, 'w') as onusDeletadas:
        for onu in listaONU:
            onusDeletadas.write(f'ont delete {gPON} {onu["ID"]}\n')

    print(f'Comandos de exclusão salvos em {ONTdeleteTXT}')

    # Cria o arquivo currentONTcommand.txt com os comandos "ont delete {ID}"
    with open(currentONT, 'w') as currentONUs:
        for onu in listaONU:
            currentONUs.write(f'display current-configuration ont {PON_ANTIGA} {onu["ID"]}\n')

    print(f'Comandos de exclusão salvos em {currentONT}')


    # Lê os comandos do arquivo delete_commands.txt para uma lista
    with open(ONTdeleteTXT, 'r') as onusDeletadas:
        deletaCommands = onusDeletadas.readlines()

    # Lê os comandos do arquivo currentONTcommand.txt para uma lista
    with open(currentONT, 'r') as currentONUs:
        commandcurrentONUs = currentONUs.readlines()

    # Comandos para pegar service port
    commandsCurrentONT = [
        "enable",
        "config",
    ]

    # Função de conexão SSH e execução dos comandos
    def ssh_connect_and_executeCurrentONU(hostname, username, password, commandsCurrentONT, commandcurrentONUs, delay=0, timeout=1):
        # Cria um cliente SSH
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Conecta ao host via SSH com timeout
            client.connect(hostname, username=username, password=password, timeout=timeout)

            # Cria um shell interativo
            ssh_shell = client.invoke_shell()

            # Executa os comandos iniciais no shell
            for command in commandsCurrentONT:
                ssh_shell.send(command + '\n')
                time.sleep(delay)  # Aguarda um tempo para o comando ser processado

            # Executa os comandos de exclusão
            for command in commandcurrentONUs:
                ssh_shell.send(command + '\n')
                time.sleep(delay)  # Aguarda um tempo para o comando ser processado

                # Aguarda até que o comando seja processado
                output = ""
                end_time = time.time() + timeout
                while time.time() < end_time:
                    if ssh_shell.recv_ready():
                        output += ssh_shell.recv(4096).decode('utf-8')
                        
                        # Verifica se a resposta contém a solicitação de Enter
                        if "{ <cr>||<K> }" in output:
                            ssh_shell.send('\n')  # Envia Enter para continuar
                            time.sleep(delay)  # Aguarda após o Enter
                    else:
                        time.sleep(0.5)  # Aguarda um pouco antes de verificar novamente

                print(output)

        except Exception as e:
            print(f"Erro ao conectar ou executar comandos: {e}")
        finally:
            # Fecha a conexão SSH
            client.close()

    # Executa a função
    ssh_connect_and_executeCurrentONU(hostname, username, password, commandsCurrentONT, commandcurrentONUs, delay=0, timeout=1)

"""
    # Comandos para deltar ONU
    commandsDeletaONU = [
        "enable",
        "config",
        f"interface gpon {interfaceGPON}",
    ]

    # Função de conexão SSH e execução dos comandos
    def ssh_connect_and_executeDeleteONU(hostname, username, password, commandsDeletaONU, deletaCommands, delay=0.1, timeout=2):
        # Cria um cliente SSH
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Conecta ao host via SSH com timeout
            client.connect(hostname, username=username, password=password, timeout=timeout)

            # Cria um shell interativo
            ssh_shell = client.invoke_shell()

            # Executa os comandos iniciais no shell
            for command in commandsDeletaONU:
                ssh_shell.send(command + '\n')
                time.sleep(delay)  # Aguarda um tempo para o comando ser processado

            # Executa os comandos de exclusão
            for command in deletaCommands:
                ssh_shell.send(command + '\n')
                time.sleep(delay)  # Aguarda um tempo para o comando ser processado

                # Aguarda até que o comando seja processado
                output = ""
                end_time = time.time() + timeout
                while time.time() < end_time:
                    if ssh_shell.recv_ready():
                        output += ssh_shell.recv(4096).decode('utf-8')
                        
                        # Verifica se a resposta contém a solicitação de Enter
                        if "{ <cr>||<K> }" in output:
                            ssh_shell.send('\n')  # Envia Enter para continuar
                            time.sleep(delay)  # Aguarda após o Enter
                    else:
                        time.sleep(0.5)  # Aguarda um pouco antes de verificar novamente

                print(output)

        except Exception as e:
            print(f"Erro ao conectar ou executar comandos: {e}")
        finally:
            # Fecha a conexão SSH
            client.close()

    # Executa a função
    ssh_connect_and_executeDeleteONU(hostname, username, password, commandsDeletaONU, deletaCommands, delay=0.1, timeout=2)
"""
while True:
     continuar = input('Deseja continuar? Digite "s" para Sim ou "n" para Não: ').lower()
     if continuar not in ['s', 'n']:
        print('Por favor, responda "s" ou "n".')
     elif continuar == 's':
         deleta_onu()
         #print("Fim do Script\nAdeus!")
         break
     else:
         #print("Fim do Programa\nAdeus!")
         break

