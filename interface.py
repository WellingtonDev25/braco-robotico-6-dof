import os
import sys
import json
import time
import pickle
import threading
import serial
import customtkinter as ctk
from tkinter import messagebox

# =========================================================
# ARQUIVOS
# =========================================================
NOME_ARQUIVO_CONFIG = "config.json"


def obter_pasta_base():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


PASTA_BASE = obter_pasta_base()
ARQUIVO_CONFIG = os.path.join(PASTA_BASE, NOME_ARQUIVO_CONFIG)

CONFIG_PADRAO = {
    "porta_arduino": "COM5",
    "baudrate": 115200,
    "arquivo_gravacao": "movimentos_servos.pkl",
    "servos": {
        "Base": {
            "canal": 1,
            "min": 0,
            "max": 180,
            "inicial": 74
        },
        "Ombro": {
            "canal": 2,
            "min": 0,
            "max": 120,
            "inicial": 24
        },
        "Cotovelo": {
            "canal": 3,
            "min": 0,
            "max": 180,
            "inicial": 180
        },
        "Pulso": {
            "canal": 4,
            "min": 0,
            "max": 180,
            "inicial": 77
        },
        "Rotação Garra": {
            "canal": 5,
            "min": 0,
            "max": 180,
            "inicial": 128
        },
        "Garra": {
            "canal": 6,
            "min": 0,
            "max": 180,
            "inicial": 116
        }
    }
}


def criar_config_padrao():
    with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(CONFIG_PADRAO, f, indent=4, ensure_ascii=False)


def carregar_config():
    if not os.path.exists(ARQUIVO_CONFIG):
        criar_config_padrao()

    with open(ARQUIVO_CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


CONFIG = carregar_config()

PORTA_ARDUINO = CONFIG.get("porta_arduino", "COM5")
BAUDRATE = int(CONFIG.get("baudrate", 115200))
ARQUIVO_GRAVACAO = os.path.join(
    PASTA_BASE,
    CONFIG.get("arquivo_gravacao", "movimentos_servos.pkl")
)

SERVOS_CONFIG = CONFIG.get("servos", {})

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Controle PCA9685 - Braço Robótico")
        self.geometry("1120x780")
        self.minsize(1020, 700)

        self.ser = None
        self.sliders = {}
        self.labels_valor = {}
        self.labels_limites = {}

        self.enviando_em_lote = False
        self.executando_movimento = False

        self.gravando = False
        self.movimentos_gravados = []
        self.tempo_inicio_gravacao = None

        self.protocol("WM_DELETE_WINDOW", self.fechar_app)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.validar_config_servos()
        self.criar_interface()
        self.conectar_serial()

    # =====================================================
    # HELPERS
    # =====================================================
    def validar_config_servos(self):
        for nome, dados in SERVOS_CONFIG.items():
            ang_min = int(dados.get("min", 0))
            ang_max = int(dados.get("max", 180))
            if ang_min > ang_max:
                ang_min, ang_max = ang_max, ang_min
            dados["min"] = ang_min
            dados["max"] = ang_max

            ang_inicial = int(dados.get("inicial", 90))
            dados["inicial"] = max(ang_min, min(ang_max, ang_inicial))

    def obter_limites(self, nome_servo):
        dados = SERVOS_CONFIG.get(nome_servo, {})
        return int(dados.get("min", 0)), int(dados.get("max", 180))

    def obter_canal(self, nome_servo):
        return int(SERVOS_CONFIG[nome_servo]["canal"])

    def obter_angulo_inicial(self, nome_servo):
        return int(SERVOS_CONFIG[nome_servo].get("inicial", 90))

    def limitar_angulo_por_nome(self, nome_servo, angulo):
        ang_min, ang_max = self.obter_limites(nome_servo)
        return max(ang_min, min(ang_max, int(angulo)))

    def obter_nome_por_canal(self, canal):
        for nome, dados in SERVOS_CONFIG.items():
            if int(dados.get("canal", -1)) == canal:
                return nome
        return None

    # =====================================================
    # INTERFACE
    # =====================================================
    def criar_interface(self):
        titulo = ctk.CTkLabel(
            self,
            text="Controle de Servos via Arduino + PCA9685",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        titulo.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="n")

        self.frame_principal = ctk.CTkFrame(self, corner_radius=15)
        self.frame_principal.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.frame_principal.grid_columnconfigure(0, weight=1)
        self.frame_principal.grid_rowconfigure(0, weight=1)

        self.frame_servos = ctk.CTkScrollableFrame(
            self.frame_principal,
            label_text="Servos do braço"
        )
        self.frame_servos.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        self.frame_servos.grid_columnconfigure(1, weight=1)

        cab1 = ctk.CTkLabel(self.frame_servos, text="Servo", font=ctk.CTkFont(weight="bold"))
        cab1.grid(row=0, column=0, padx=10, pady=(5, 10), sticky="w")

        cab2 = ctk.CTkLabel(self.frame_servos, text="Controle", font=ctk.CTkFont(weight="bold"))
        cab2.grid(row=0, column=1, padx=10, pady=(5, 10), sticky="w")

        cab3 = ctk.CTkLabel(self.frame_servos, text="Ângulo", font=ctk.CTkFont(weight="bold"))
        cab3.grid(row=0, column=2, padx=10, pady=(5, 10))

        cab4 = ctk.CTkLabel(self.frame_servos, text="Limites", font=ctk.CTkFont(weight="bold"))
        cab4.grid(row=0, column=3, padx=10, pady=(5, 10))

        linha = 1
        for nome, dados in SERVOS_CONFIG.items():
            canal = int(dados["canal"])
            ang_min, ang_max = self.obter_limites(nome)
            ang_inicial = self.obter_angulo_inicial(nome)

            lbl_nome = ctk.CTkLabel(
                self.frame_servos,
                text=f"{nome} (canal {canal})",
                font=ctk.CTkFont(size=16, weight="bold"),
                width=180
            )
            lbl_nome.grid(row=linha, column=0, padx=10, pady=12, sticky="w")

            passos = max(1, ang_max - ang_min)

            slider = ctk.CTkSlider(
                self.frame_servos,
                from_=ang_min,
                to=ang_max,
                number_of_steps=passos,
                command=lambda valor, n=nome: self.on_slider_change(n, valor)
            )
            slider.grid(row=linha, column=1, padx=10, pady=12, sticky="ew")
            slider.set(ang_inicial)

            lbl_valor = ctk.CTkLabel(
                self.frame_servos,
                text=f"{ang_inicial}°",
                width=60
            )
            lbl_valor.grid(row=linha, column=2, padx=10, pady=12)

            lbl_limites = ctk.CTkLabel(
                self.frame_servos,
                text=f"{ang_min}° a {ang_max}°",
                width=100
            )
            lbl_limites.grid(row=linha, column=3, padx=10, pady=12)

            self.sliders[nome] = slider
            self.labels_valor[nome] = lbl_valor
            self.labels_limites[nome] = lbl_limites

            linha += 1

        self.frame_botoes = ctk.CTkFrame(self.frame_principal)
        self.frame_botoes.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="ew")
        self.frame_botoes.grid_columnconfigure((0, 1, 2), weight=1)

        btn_pos_inicial = ctk.CTkButton(
            self.frame_botoes,
            text="Ir para Posição Inicial",
            command=self.ir_para_posicao_inicial
        )
        btn_pos_inicial.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.btn_gravar = ctk.CTkButton(
            self.frame_botoes,
            text="Gravar Movimentos",
            command=self.toggle_gravacao
        )
        self.btn_gravar.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.btn_executar = ctk.CTkButton(
            self.frame_botoes,
            text="Executar Movimento Salvo",
            command=self.executar_movimento_salvo
        )
        self.btn_executar.grid(row=0, column=2, padx=10, pady=10, sticky="ew")

        self.status_label = ctk.CTkLabel(
            self,
            text="Status: aguardando conexão...",
            anchor="w"
        )
        self.status_label.grid(row=2, column=0, padx=20, pady=(0, 15), sticky="ew")

    # =====================================================
    # SERIAL
    # =====================================================
    def conectar_serial(self):
        try:
            self.status(f"Conectando ao Arduino em {PORTA_ARDUINO}...")
            self.ser = serial.Serial(PORTA_ARDUINO, BAUDRATE, timeout=1)
            time.sleep(2.5)

            resposta = self.ler_linhas_por_tempo(3)
            print("Resposta inicial:", resposta)

            self.status("Arduino conectado com sucesso.")
            self.after(300, self.ir_para_posicao_inicial)

        except Exception as e:
            self.status("Erro de conexão.")
            messagebox.showerror(
                "Erro",
                f"Não foi possível conectar na porta {PORTA_ARDUINO}.\n\n"
                f"Edite o arquivo '{NOME_ARQUIVO_CONFIG}' se precisar trocar a porta.\n\n"
                f"Detalhes: {e}"
            )

    def ler_linhas_por_tempo(self, segundos=1.5):
        fim = time.time() + segundos
        linhas = []

        while time.time() < fim:
            try:
                if self.ser and self.ser.in_waiting:
                    linha = self.ser.readline().decode(errors="ignore").strip()
                    if linha:
                        linhas.append(linha)
            except Exception:
                pass
            time.sleep(0.05)

        return linhas

    def enviar_comando(self, texto):
        if not self.ser or not self.ser.is_open:
            return False
        try:
            self.ser.write((texto + "\n").encode())
            return True
        except Exception as e:
            print("Erro ao enviar comando:", e)
            return False

    # =====================================================
    # GRAVAÇÃO
    # =====================================================
    def toggle_gravacao(self):
        if self.executando_movimento:
            messagebox.showwarning("Aviso", "Não é possível gravar enquanto um movimento salvo está sendo executado.")
            return

        if not self.gravando:
            self.iniciar_gravacao()
        else:
            self.parar_gravacao()

    def iniciar_gravacao(self):
        if os.path.exists(ARQUIVO_GRAVACAO):
            resposta = messagebox.askyesno(
                "Sobrescrever gravação",
                "Já existe uma gravação salva.\n\nSe continuar, ela será sobrescrita.\n\nDeseja continuar?"
            )
            if not resposta:
                return

        self.movimentos_gravados = []
        self.tempo_inicio_gravacao = time.time()
        self.gravando = True

        self.btn_gravar.configure(text="Parar Gravação", fg_color="#c67f00", hover_color="#a56600")
        self.status("Gravação iniciada. Movimente os servos pelos sliders.")

    def parar_gravacao(self):
        self.gravando = False
        self.btn_gravar.configure(
            text="Gravar Movimentos",
            fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"],
            hover_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"]
        )

        if not self.movimentos_gravados:
            self.status("Gravação parada. Nenhum movimento foi registrado.")
            messagebox.showinfo("Gravação", "Nenhum movimento foi registrado.")
            return

        dados = {
            "criado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
            "movimentos": self.movimentos_gravados
        }

        try:
            with open(ARQUIVO_GRAVACAO, "wb") as f:
                pickle.dump(dados, f)

            self.status(f"Gravação salva em '{os.path.basename(ARQUIVO_GRAVACAO)}'.")
            messagebox.showinfo(
                "Gravação",
                f"Movimentos salvos com sucesso.\n\nArquivo: {os.path.basename(ARQUIVO_GRAVACAO)}"
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível salvar a gravação.\n\n{e}")

    def registrar_movimento(self, nome_servo, angulo):
        if not self.gravando or self.executando_movimento:
            return

        if self.tempo_inicio_gravacao is None:
            self.tempo_inicio_gravacao = time.time()

        tempo_relativo = time.time() - self.tempo_inicio_gravacao
        canal = self.obter_canal(nome_servo)

        self.movimentos_gravados.append({
            "t": tempo_relativo,
            "servo": nome_servo,
            "canal": int(canal),
            "angulo": int(angulo)
        })

    def executar_movimento_salvo(self):
        if self.gravando:
            messagebox.showwarning("Aviso", "Pare a gravação antes de executar um movimento salvo.")
            return

        if self.executando_movimento:
            messagebox.showwarning("Aviso", "Já existe uma execução em andamento.")
            return

        if not os.path.exists(ARQUIVO_GRAVACAO):
            messagebox.showwarning("Aviso", "Nenhuma gravação salva foi encontrada.")
            return

        threading.Thread(target=self._executar_movimento_salvo_thread, daemon=True).start()

    def _executar_movimento_salvo_thread(self):
        try:
            self.executando_movimento = True
            self.enviando_em_lote = True
            self.btn_executar.configure(state="disabled")
            self.btn_gravar.configure(state="disabled")

            with open(ARQUIVO_GRAVACAO, "rb") as f:
                dados = pickle.load(f)

            movimentos = dados.get("movimentos", [])

            if not movimentos:
                self.status("Arquivo de gravação vazio.")
                messagebox.showwarning("Aviso", "A gravação está vazia.")
                return

            self.status("Executando movimento salvo...")

            tempo_anterior = 0.0

            for mov in movimentos:
                tempo_atual = float(mov["t"])
                canal = int(mov["canal"])
                nome = mov.get("servo") or self.obter_nome_por_canal(canal)
                if nome is None:
                    continue

                angulo = self.limitar_angulo_por_nome(nome, int(mov["angulo"]))

                espera = max(0.0, tempo_atual - tempo_anterior)
                time.sleep(espera)

                self.enviar_comando(f"{canal},{angulo}")

                if nome in self.sliders:
                    self.after(0, lambda n=nome, a=angulo: self.sliders[n].set(a))
                    self.after(0, lambda n=nome, a=angulo: self.labels_valor[n].configure(text=f"{a}°"))

                tempo_anterior = tempo_atual

            self.status("Execução da gravação concluída.")

        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível executar a gravação.\n\n{e}")
            self.status("Erro ao executar gravação.")
        finally:
            self.executando_movimento = False
            self.enviando_em_lote = False
            self.after(0, lambda: self.btn_executar.configure(state="normal"))
            self.after(0, lambda: self.btn_gravar.configure(state="normal"))

    # =====================================================
    # CONTROLE
    # =====================================================
    def on_slider_change(self, nome_servo, valor):
        angulo = self.limitar_angulo_por_nome(nome_servo, int(float(valor)))
        canal = self.obter_canal(nome_servo)

        self.labels_valor[nome_servo].configure(text=f"{angulo}°")

        if self.enviando_em_lote:
            return

        self.enviar_comando(f"{canal},{angulo}")
        self.registrar_movimento(nome_servo, angulo)

    def ir_para_posicao_inicial(self):
        if self.executando_movimento:
            messagebox.showwarning("Aviso", "Aguarde o término da execução do movimento salvo.")
            return
        threading.Thread(target=self._ir_para_posicao_inicial_thread, daemon=True).start()

    def _ir_para_posicao_inicial_thread(self):
        self.enviando_em_lote = True

        for nome in SERVOS_CONFIG.keys():
            canal = self.obter_canal(nome)
            angulo = self.obter_angulo_inicial(nome)

            self.after(0, lambda n=nome, a=angulo: self.sliders[n].set(a))
            self.after(0, lambda n=nome, a=angulo: self.labels_valor[n].configure(text=f"{a}°"))

            self.enviar_comando(f"{canal},{angulo}")
            time.sleep(0.18)

        self.status("Servos movidos para a posição inicial.")
        self.enviando_em_lote = False

    def status(self, texto):
        self.after(0, lambda: self.status_label.configure(text=f"Status: {texto}"))

    def fechar_app(self):
        try:
            if self.gravando:
                resposta = messagebox.askyesno(
                    "Gravação em andamento",
                    "A gravação ainda está em andamento.\n\nDeseja parar e sair?"
                )
                if not resposta:
                    return
                self.parar_gravacao()

            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()