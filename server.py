import socket
import os
import hashlib
import time
import threading
import config

def calcular_md5(dados):
    return hashlib.md5(dados).hexdigest()

def iniciar_servidor():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((config.SERVER_IP, config.SERVER_PORT))
    server_socket.settimeout(1.0)

    print(f"Servidor UDP rodando em {config.SERVER_IP}:{config.SERVER_PORT}")
    print("Aguardando requisições...")

    try: 
        while True:
            try:
                mensagem, endereco_cliente = server_socket.recvfrom(config.BUFFER_SIZE)
                
                msg_decodificada = mensagem.decode(config.ENCODING)
                partes = msg_decodificada.split(config.SEPARATOR.decode(config.ENCODING))

                if partes[0] == "GET" and len(partes) > 1:
                    nome_arquivo = partes[1]
                    print(f"\nRequisição de {endereco_cliente}. Criando Thread...")
                    
                    # O servidor principal delega o trabalho e não fica bloqueado para um cliente só
                    thread_cliente = threading.Thread(target=enviar_arquivo, args=(endereco_cliente, nome_arquivo), daemon=True)
                    thread_cliente.start()
                else:
                    print("Comando não reconhecido.")
            except socket.timeout:
                pass 
            except Exception as e:
                print(f"Erro ao processar: {e}")
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server_socket.close() 

def enviar_arquivo(endereco_cliente, nome_arquivo):
    # Socket exclusivo para essa sessão, o SO delega uma porta aleatória vazia para tratar.
    sessao_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        if not os.path.exists(nome_arquivo):
            print(f"Arquivo '{nome_arquivo}' não encontrado.")
            msg_erro = f"ERROR{config.SEPARATOR.decode(config.ENCODING)}Arquivo nao encontrado"
            sessao_socket.sendto(msg_erro.encode(config.ENCODING), endereco_cliente)
            return

        print(f"Thread iniciada: Transferindo '{nome_arquivo}' para {endereco_cliente}")

        with open(nome_arquivo, 'rb') as f:
            seq_num = 0
            while True:
                chunk = f.read(config.CHUNK_SIZE)
                if not chunk: break 

                hash_chunk = calcular_md5(chunk)
                cabecalho = f"DATA{config.SEPARATOR.decode(config.ENCODING)}{seq_num}{config.SEPARATOR.decode(config.ENCODING)}{hash_chunk}{config.SEPARATOR.decode(config.ENCODING)}".encode(config.ENCODING)
                
                # Envia usando o Socket Exclusivo
                sessao_socket.sendto(cabecalho + chunk, endereco_cliente)
                seq_num += 1
                time.sleep(0.005)

        msg_fim = f"EOF{config.SEPARATOR.decode(config.ENCODING)}{seq_num}".encode(config.ENCODING)
        sessao_socket.sendto(msg_fim, endereco_cliente)

        # Loop de Retransmissão da Thread
        sessao_socket.settimeout(5.0) 
        while True:
            try:
                # Escuta NACKs no Socket Exclusivo
                msg, _ = sessao_socket.recvfrom(config.BUFFER_SIZE)
                texto = msg.decode(config.ENCODING)

                if texto == "FINALIZADO":
                    print(f"Transferência para {endereco_cliente} finalizada com sucesso!")
                    break
                
                elif texto.startswith("NACK"):
                    _, seq_perdido = texto.split(config.SEPARATOR.decode(config.ENCODING))
                    seq_perdido = int(seq_perdido)
                    
                    with open(nome_arquivo, 'rb') as f:
                        f.seek(seq_perdido * config.CHUNK_SIZE)
                        chunk = f.read(config.CHUNK_SIZE)
                        hash_chunk = calcular_md5(chunk)
                        cabecalho = f"DATA{config.SEPARATOR.decode(config.ENCODING)}{seq_perdido}{config.SEPARATOR.decode(config.ENCODING)}{hash_chunk}{config.SEPARATOR.decode(config.ENCODING)}".encode(config.ENCODING)
                        sessao_socket.sendto(cabecalho + chunk, endereco_cliente)
                        
            except socket.timeout:
                print(f"Tempo esgotado (Thread {endereco_cliente}). Finalizando sessão.")
                break

    except Exception as e:
        print(f"Erro na Thread de {endereco_cliente}: {e}")
    finally:
        sessao_socket.close() # Libera a porta aleatória devolvendo pro SO

if __name__ == "__main__":
    iniciar_servidor()