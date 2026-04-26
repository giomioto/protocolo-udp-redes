import socket
import hashlib
import random
import time
import config

def calcular_md5(dados):
    return hashlib.md5(dados).hexdigest()

def montar_arquivo_final(nome_arquivo, buffer_arquivo):
    nome_saida = f"recebido_{nome_arquivo}"
    print(f"Salvando no disco: {nome_saida}")
    with open(nome_saida, 'wb') as f:
        chaves_ordenadas = sorted(buffer_arquivo.keys())
        for seq in chaves_ordenadas:
            f.write(buffer_arquivo[seq])
    print("Operação concluída com sucesso!\n")

def iniciar_cliente():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(2.0)
    
    # Salva o endereço original do PORTEIRO (Porta 2004)
    ENDERECO_PRINCIPAL = (config.SERVER_IP, config.SERVER_PORT)

    while True:
        nome_arquivo = input("Digite o nome do arquivo (ou 'sair' para encerrar): ")
        
        if nome_arquivo.lower() == 'sair':
            print("Encerrando o cliente.")
            break
        
        simular_perda = input("Deseja simular perda de pacotes na rede? (s/n): ").lower() == 's'

        # RESET: Garante que a requisição GET sempre vá para a porta principal (2004)
        endereco_servidor = ENDERECO_PRINCIPAL
        
        requisicao = f"GET{config.SEPARATOR.decode(config.ENCODING)}{nome_arquivo}"
        client_socket.sendto(requisicao.encode(config.ENCODING), endereco_servidor)

        buffer_arquivo = {}
        total_esperado = 0
        houve_erro = False # Flag para saber se precisamos pular a montagem do arquivo
        
        print("\nRecebendo dados...")

        try:
            while True:
                # Endereço de onde o pacote veio (Pode ser a porta aleatória da Thread)
                pacote, addr_remetente = client_socket.recvfrom(config.BUFFER_SIZE)
                
                # Atualiza o destino para o cliente mandar NACKs direto pra Thread
                endereco_servidor = addr_remetente
                
                partes = pacote.split(config.SEPARATOR, 3)
                tipo_msg = partes[0].decode(config.ENCODING)

                if tipo_msg == "ERROR":
                    print(f"O servidor respondeu com ERRO: {partes[1].decode(config.ENCODING)}\n")
                    houve_erro = True
                    break # Quebra o loop de recepção e volta pro input

                elif tipo_msg == "EOF":
                    total_esperado = int(partes[1].decode(config.ENCODING))
                    print(f"\nEOF recebido. O arquivo tem {total_esperado} pacotes.")
                    break

                elif tipo_msg == "DATA":
                    seq_num = int(partes[1].decode(config.ENCODING))
                    hash_recebido = partes[2].decode(config.ENCODING)
                    payload_binario = partes[3]

                    if simular_perda and random.random() < 0.15:
                        print(f"    [SIMULAÇÃO] Pacote {seq_num} foi 'perdido' na rede de propósito.")
                        continue 

                    hash_calculado = calcular_md5(payload_binario)
                    
                    if hash_calculado == hash_recebido:
                        buffer_arquivo[seq_num] = payload_binario
                        print(f"    [OK] Pacote {seq_num} recebido e validado (MD5 confere).")
                    else:
                        print(f"    [CORROMPIDO] Pacote {seq_num} falhou no MD5!")

            # Se o arquivo não existia, pula a parte de recuperação e volta lá pra cima
            if houve_erro:
                continue

            # Recuperação dos pacotes faltantes
            while len(buffer_arquivo) < total_esperado:
                todos_numeros = set(range(total_esperado))
                recebidos = set(buffer_arquivo.keys())
                faltantes = todos_numeros - recebidos
                
                print(f"\nFaltam {len(faltantes)} pacotes. Iniciando resgate (NACK)...")
                
                for seq_faltante in faltantes:
                    req_nack = f"NACK{config.SEPARATOR.decode(config.ENCODING)}{seq_faltante}".encode(config.ENCODING)
                    client_socket.sendto(req_nack, endereco_servidor)
                    
                    try:
                        pacote_rec, _ = client_socket.recvfrom(config.BUFFER_SIZE)
                        partes_rec = pacote_rec.split(config.SEPARATOR, 3)
                        
                        if partes_rec[0].decode(config.ENCODING) == "DATA":
                            seq_rec = int(partes_rec[1].decode(config.ENCODING))
                            if calcular_md5(partes_rec[3]) == partes_rec[2].decode(config.ENCODING):
                                buffer_arquivo[seq_rec] = partes_rec[3]
                                print(f"    Resgate OK: Pacote {seq_rec} recuperado com sucesso!")
                    except socket.timeout:
                        pass 
                    
                    time.sleep(0.01)
            
            print("\nTodos os pacotes recebidos e validados!")
            client_socket.sendto("FINALIZADO".encode(config.ENCODING), endereco_servidor)
            montar_arquivo_final(nome_arquivo, buffer_arquivo)

        except socket.timeout:
            print("Tempo de espera esgotado. Nenhuma resposta do servidor.\n")
        except ConnectionResetError:
            print("Erro [WinError 10054]: O servidor parece estar offline ou a porta está fechada.\n")
        except Exception as e:
            print(f"Erro fatal: {e}\n")

if __name__ == "__main__":
    iniciar_cliente()