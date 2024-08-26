import paramiko
import time
import re
import os
import json
from public.dadosConexaoOLTs import *

# Mapeamento das OLTs e seus IPs
olt_IPS = {
    "OLT-SEA01": ip_SEA01,
    "OLT-SEA03": ip_SEA03,
    "OLT-VTA01": ip_VTA01,
    "OLT-VTA02": ip_VTA02,
    "OLT-VVA01": ip_VVA01,
    "OLT-VVA03": ip_VVA03,
    "OLT-CCA01": ip_CCA01,
}
#------------------------------------------------------------------------------------------------------------
#OBS: 1º adicione as ONUS que serão autorizadas, pelo comando display ont autofind all 

# Seleciona a OLT Antiga
use_OLT_Antiga = "OLT-SEA01"
pon_ANTIGA = "0/5/5"

# Seleciona a OLT Nova
use_OLT_Nova = "OLT-SEA03"

# VLAN do serviço
vlan_IN = 1502

# VLAN de saída para ONU
vlan_OUT = 1921

# Inicializa variáveis
onu_ID = 0
ont_SRV_PROF = 1921
ont_LIN_PROF = 1921
gem_PORT = 126

#------------------------------------------------------------------------------------------------------------


# Arquivo contendo a lista de ONUs
onu_FILE = 'auto_find_onu_huawei.txt'

# Arquivo contendo as descrições das ONUs
onu_FILE_DESC = 'src/onu_huawei_desc.txt'

lista_ONUS = 'lista_ONUS_hw.txt'
lista_SRV = 'lista_ONUS_hw_srv.txt'

hostnameOLTAntiga = olt_IPS.get(use_OLT_Antiga)
hostnameOLTNova = olt_IPS.get(use_OLT_Nova)

# Dados de acesso SSH
username = user
password = user_password

#PEGA O SUMMARY------------------------------------------------------------------------------------------------------------

# Comandos para a OLT
commandsSummary = [
    "enable",
    "config",
    f"display ont info summary {pon_ANTIGA} | no-more"
]

def ssh_connect_and_executeSummary(hostnameOLTAntiga, username, password, commandsSummary, delay=0.2, timeout=6, max_loops=10):
    # Cria um cliente SSH
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # Conecta ao host via SSH com timeout
        client.connect(hostnameOLTAntiga, username=username, password=password, timeout=timeout)

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
        with open('src/onu_huawei_desc.txt', 'w') as file:
            file.write('\n'.join(onu_huawei_desc))

        print("As linhas filtradas foram salvas em 'src/onu_huawei_desc.txt'.")

    except Exception as e:
        print(f"Erro ao conectar ou executar comandos: {e}")
    finally:
        # Fecha a conexão SSH
        client.close()

# Executa a função
ssh_connect_and_executeSummary(hostnameOLTAntiga, username, password, commandsSummary, delay=0.2, timeout=6, max_loops=10)

#FORMULA AS LISTA DE ONUS E SERVICE-PORT------------------------------------------------------------------------------------------------------------

# Limpa os arquivos de saída
open(lista_ONUS, 'w').close()
open(lista_SRV, 'w').close()

# Lê o arquivo de ONUs e armazena o número total de ONUs
with open(onu_FILE, 'r') as f:
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

    with open(onu_FILE_DESC, 'r') as f:
        onu_desc_lines = f.readlines()
    
    onu_desc = next((line.split()[5] for line in onu_desc_lines if ONU_SN[8:16] in line), ONU_SN)

    with open(lista_ONUS, 'a') as lista_ONUS_file:
        lista_ONUS_file.write(f'ont add {pon_id} {onu_ID} sn-auth {ONU_SN} omci ont-lineprofile-id {ont_LIN_PROF} ont-srvprofile-id {ont_SRV_PROF} desc "{onu_desc}"\n\n')
        
        if onu_oper == "ROUTER":
            for i in range(1, 5):
                lista_ONUS_file.write(f'ont port route {pon_id} {onu_ID} eth {i} enable\n\n')
        else:
            lista_ONUS_file.write(f'ont port native-vlan {pon_id} {onu_ID} eth 1 vlan {vlan_OUT} priority 0\n\n')

    with open(lista_SRV, 'a') as lista_SRV_file:
        contServiceport = contServiceport + 1
        if onu_oper == "ROUTER":
            lista_SRV_file.write(f'service-port vlan {vlan_OUT} gpon {porta_pon} ont {onu_ID} gemport {gem_PORT} multi-service user-vlan untagged tag-transform default\n\n')
        else:
            lista_SRV_file.write(f'service-port vlan {vlan_IN} gpon {porta_pon} ont {onu_ID} gemport {gem_PORT} multi-service user-vlan {vlan_OUT} tag-transform translate\n\n')

    onu_ID += 1

# Exibe o conteúdo dos arquivos gerados
with open(lista_ONUS, 'r') as lista_ONUS_file:
    #print(lista_ONUS_file.read())
    print("A lista de ONUs foi gerada!")

with open(lista_SRV, 'r') as lista_SRV_file:
    #print(lista_SRV_file.read())
    print("A lista de service-port foi gerada!")

#INICIO FUNÇÃO DELTA ONU------------------------------------------------------------------------------------------------------------

def main():    
    # Definindo o nome dos arquivos de entrada e saída
    onu_huawei_descJSON = 'src/onu_huawei_desc.json'
    ONTdeleteTXT = 'ontDelete.txt'
    seviceportdeleteTXT = 'undo_service_ports.txt'
    ONTaddTXT = 'lista_ONUS_hw.txt'
    serviceportAddTXT = 'lista_ONUS_hw_srv.txt'
    currentONT = 'src/currentONT.txt'

    # Definindo a interface GPON com base em pon_ANTIGA
    interfaceGPON_Antiga = "/".join(pon_ANTIGA.split("/")[0:2])
    gPON_Antiga = "/".join(pon_ANTIGA.split("/")[2:3])

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
    with open(onu_FILE_DESC, 'r') as file:
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
            onusDeletadas.write(f'ont delete {gPON_Antiga} {onu["ID"]}\n\n')

    print(f'Comandos de exclusão salvos em {ONTdeleteTXT}')

    # Cria o arquivo currentONTcommand.txt com os comandos "ont delete {ID}"
    with open(currentONT, 'w') as currentONUs:
        for onu in listaONU:
            currentONUs.write(f'display current-configuration ont {pon_ANTIGA} {onu["ID"]}\n')

    print(f'Comandos de exclusão salvos em {currentONT}')

    # Lê os comandos do arquivo currentONTcommand.txt para uma lista
    with open(currentONT, 'r') as currentONUs:
        commandcurrentONUs = currentONUs.readlines()

#FUNÇÃO PEGA CURRENT CONFIGURATION------------------------------------------------------------------------------------------------------------

    # Comandos para pegar service port
    commandsCurrentONT = [
        "enable",
        "config",
    ]

    # Função de conexão SSH e execução dos comandos
    def ssh_connect_and_executeCurrentONU(hostnameOLTAntiga, username, password, commandsCurrentONT, commandcurrentONUs, delay=0.2, timeout=6):
        # Cria um cliente SSH
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Conecta ao host via SSH com timeout
            client.connect(hostnameOLTAntiga, username=username, password=password, timeout=timeout)

            # Cria um shell interativo
            ssh_shell = client.invoke_shell()

            # Executando os comandos e filtrando a saída
            service_port_lines = []

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

                #print(output)

                # Filtrando apenas as linhas que contêm 'service-port'
                lines = output.splitlines()
                for line in lines:
                    if 'service-port' in line:
                        service_port_lines.append(line)

            # Salvando as linhas filtradas em um arquivo
            with open('src/service_port_lines.txt', 'w') as file:
                for line in service_port_lines:
                    file.write(line + '\n')

            print("As linhas 'service-port' foram salvas em 'src/service_port_lines.txt'.")

            # Nome do arquivo de entrada e saída
            file_service_port_lines = 'src/service_port_lines.txt'
            file_undo_service_ports = 'undo_service_ports.txt'

            # Leitura do arquivo de entrada
            with open(file_service_port_lines, 'r') as file:
                lines = file.readlines()

            # Processamento das linhas para criar os comandos "undo service-port ID"
            undo_lines = []
            for line in lines:
                if 'service-port' in line:
                    # Extraindo o ID do service-port (a segunda palavra na linha)
                    service_port_id = line.split()[1]
                    undo_line = f"undo service-port {service_port_id}\n\n"
                    undo_lines.append(undo_line)

            # Salvando os comandos "undo" no arquivo de saída
            with open(file_undo_service_ports, 'w') as file:
                file.writelines(undo_lines)

            print(f"Comandos 'undo' gerados e salvos em '{file_undo_service_ports}'.")


        except Exception as e:
            print(f"Erro ao conectar ou executar comandos: {e}")
        finally:
            # Fecha a conexão SSH
            client.close()

    # Executa a função
    ssh_connect_and_executeCurrentONU(hostnameOLTAntiga, username, password, commandsCurrentONT, commandcurrentONUs, delay=0.2, timeout=6)


#FUNÇÃO DELETA SERVICE-PORT------------------------------------------------------------------------------------------------------------
    
    # Lê os comandos do arquivo delete_commands.txt para uma lista
    with open(seviceportdeleteTXT, 'r') as serviceportDeletadas:
        deletaServiceportCommands = serviceportDeletadas.readlines()

    # Comandos para deletar service_port
    commandsDeletaServiceport = [
        "enable",
        "config",
    ]

    # Função de conexão SSH e execução dos comandos
    def ssh_connect_and_executeDeleteServiceport(hostnameOLTAntiga, username, password, commandsDeletaServiceport, deletaServiceportCommands, delay=0.1, timeout=2):
        # Cria um cliente SSH
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Conecta ao host via SSH com timeout
            client.connect(hostnameOLTAntiga, username=username, password=password, timeout=timeout)

            # Cria um shell interativo
            ssh_shell = client.invoke_shell()

            # Executa os comandos iniciais no shell
            for command in commandsDeletaServiceport:
                ssh_shell.send(command + '\n')
                time.sleep(delay)  # Aguarda um tempo para o comando ser processado

            # Executa os comandos de exclusão
            for command in deletaServiceportCommands:
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

                #print(output)
            
            print("Os service-port foram deletados")
        except Exception as e:
            print(f"Erro ao conectar ou executar comandos: {e}")
        finally:
            # Fecha a conexão SSH
            client.close()

    # Executa a função
    ssh_connect_and_executeDeleteServiceport(hostnameOLTAntiga, username, password, commandsDeletaServiceport, deletaServiceportCommands, delay=0.1, timeout=2)

#FUNÇÃO DELETA ONU------------------------------------------------------------------------------------------------------------
    
    # Lê os comandos do arquivo delete_commands.txt para uma lista
    with open(ONTdeleteTXT, 'r') as onusDeletadas:
        deletaONUCommands = onusDeletadas.readlines()

    # Comandos para deletar ONU
    commandsDeletaONU = [
        "enable",
        "config",
        f"interface gpon {interfaceGPON_Antiga}",
    ]

    # Função de conexão SSH e execução dos comandos
    def ssh_connect_and_executeDeleteONU(hostnameOLTAntiga, username, password, commandsDeletaONU, deletaONUCommands, delay=0.1, timeout=2):
        
        # Cria um cliente SSH
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Conecta ao host via SSH com timeout
            client.connect(hostnameOLTAntiga, username=username, password=password, timeout=timeout)

            # Cria um shell interativo
            ssh_shell = client.invoke_shell()

            # Executa os comandos iniciais no shell
            for command in commandsDeletaONU:
                ssh_shell.send(command + '\n')
                time.sleep(delay)  # Aguarda um tempo para o comando ser processado

            # Executa os comandos de exclusão
            for command in deletaONUCommands:
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

                #print(output)
            
            print("As ONUs foram deletadas")
        except Exception as e:
            print(f"Erro ao conectar ou executar comandos: {e}")
        finally:
            # Fecha a conexão SSH
            client.close()
    
    # Executa a função
    ssh_connect_and_executeDeleteONU(hostnameOLTAntiga, username, password, commandsDeletaONU, deletaONUCommands, delay=0.1, timeout=2)


#FUNÇÃO ADICIONA ONU NA NOVA OLT/PON------------------------------------------------------------------------------------------------------------
    
    interfaceGPON_Nova = "/".join(porta_pon.split("/")[0:2])
    gPON_Nova = "/".join(porta_pon.split("/")[2:3])
    

    # Lê os comandos do arquivo delete_commands.txt para uma lista
    with open(ONTaddTXT, 'r') as onusAdicionada:
        addONUCommands = onusAdicionada.readlines()
    # Comandos para adicionar ONU
    commandsONTadd = [
        "enable",
        "config",
        f"interface gpon {interfaceGPON_Nova}",
    ]

    # Função de conexão SSH e execução dos comandos
    def ssh_connect_and_executeAddONU(hostnameOLTNova, username, password, commandsONTadd, addONUCommands, delay=0.1, timeout=2):
        # Cria um cliente SSH
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Conecta ao host via SSH com timeout
            client.connect(hostnameOLTNova, username=username, password=password, timeout=timeout)

            # Cria um shell interativo
            ssh_shell = client.invoke_shell()

            # Executa os comandos iniciais no shell
            for command in commandsONTadd:
                ssh_shell.send(command + '\n')
                time.sleep(delay)  # Aguarda um tempo para o comando ser processado

            # Executa os comandos de exclusão
            for command in addONUCommands:
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

                #print(output)
            
            print(f"As ONUs foram Adicionada na nova PON {interfaceGPON_Nova}/{gPON_Nova}")
        except Exception as e:
            print(f"Erro ao conectar ou executar comandos: {e}")
        finally:
            # Fecha a conexão SSH
            client.close()
    
    # Executa a função
    ssh_connect_and_executeAddONU(hostnameOLTNova, username, password, commandsONTadd, addONUCommands, delay=0.1, timeout=2)

#FUNÇÃO ADICIONA SERVICE-PORT------------------------------------------------------------------------------------------------------------
    
    # Lê os comandos do arquivo delete_commands.txt para uma lista
    with open(serviceportAddTXT, 'r') as serviceportAdicionadas:
        adicionaServiceportCommands = serviceportAdicionadas.readlines()

    # Comandos para adiciona service_port
    commandsAdcionaServiceport = [
        "enable",
        "config",
    ]

    # Função de conexão SSH e execução dos comandos
    def ssh_connect_and_executeAdicionaServiceport(hostnameOLTNova, username, password, commandsAdcionaServiceport, adicionaServiceportCommands, delay=0.1, timeout=2):
        # Cria um cliente SSH
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Conecta ao host via SSH com timeout
            client.connect(hostnameOLTNova, username=username, password=password, timeout=timeout)

            # Cria um shell interativo
            ssh_shell = client.invoke_shell()

            # Executa os comandos iniciais no shell
            for command in commandsAdcionaServiceport:
                ssh_shell.send(command + '\n')
                time.sleep(delay)  # Aguarda um tempo para o comando ser processado

            # Executa os comandos de exclusão
            for command in adicionaServiceportCommands:
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

                #print(output)
            
            print("Os service-port foram adicionados")
        except Exception as e:
            print(f"Erro ao conectar ou executar comandos: {e}")
        finally:
            # Fecha a conexão SSH
            client.close()

    # Executa a função
    ssh_connect_and_executeAdicionaServiceport(hostnameOLTNova, username, password, commandsAdcionaServiceport, adicionaServiceportCommands, delay=0.1, timeout=2)

while True:
     continuar = input('Deseja continuar? Digite "s" para Sim ou "n" para Não: ').lower()
     if continuar not in ['s', 'n']:
        print('Por favor, responda "s" ou "n".')
     elif continuar == 's':
         main()
         print("Fim do Script\nAdeus!")
         break
     else:
         print("Fim do Programa\nAdeus!")
         break

