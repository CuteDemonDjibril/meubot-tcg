import discord
from discord.ext import commands
import json
import random

# -------------------------------------------------------------
# 1. CONFIGURAÇÃO BASE DO BOT
# -------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# GUARDE O ID DO SEU CANAL DE RANKING AQUI (Substitua pelos números do seu canal)
CANAL_RANKING_ID = 1546215738342248579/1546221019625426964 

# Estruturas globais de controle
PARTIDAS_ATIVAS = {}  # canal_id: Partida
DESAFIOS_PENDENTES = {}  # desafiado_id: {desafiante, canal_id}
RANKING_JOGADORES = {}  # user_id: {"vitorias": 0, "derrotas": 0}

# -------------------------------------------------------------
# 2. CLASSES DO JOGO (ESTADO DA PARTIDA)
# -------------------------------------------------------------
class PartidaTCG:
    def __init__(self, j1: discord.User, j2: discord.User):
        self.j1 = j1
        self.j2 = j2
        self.turno_global = 1
        self.estacao = "Dia"  # Muda para "Noite" no turno 17
        self.turno_atual = j1
        self.oponente_atual = j2
        
        # Atributos de HP (Padrão 100, ajustável)
        self.hp_j1 = 100
        self.hp_j2 = 100
        self.cargas_j1 = 0
        self.cargas_j2 = 0

    def alternar_turno(self):
        self.turno_global += 1
        
        # Controle de Estação Dia / Noite
        if self.turno_global > 16 and self.estacao == "Dia":
            self.estacao = "Noite"
            
        self.turno_atual, self.oponente_atual = self.oponente_atual, self.turno_atual

# -------------------------------------------------------------
# 3. SISTEMA DE MATCHMAKING (!pvp, !acc, !rec)
# -------------------------------------------------------------
@bot.command(name="pvp")
async def desafiar_pvp(ctx, oponente: discord.Member):
    if oponente.bot:
        await ctx.send("❌ Você não pode desafiar um bot!")
        return
        
    if oponente == ctx.author:
        await ctx.send("❌ Você não pode desafiar a si mesmo!")
        return

    if ctx.channel.id in PARTIDAS_ATIVAS:
        await ctx.send("⚠️ Já existe uma partida em andamento neste canal!")
        return

    # Registra a solicitação pendente
    DESAFIOS_PENDENTES[oponente.id] = {
        "desafiante": ctx.author,
        "canal_id": ctx.channel.id
    }

    await ctx.send(
        f"⚔️ {oponente.mention}, você foi desafiado por {ctx.author.mention} para um duelo TCG!\n"
        f"Digite **`!acc`** para aceitar ou **`!rec`** para recusar."
    )

@bot.command(name="acc")
async def aceitar_pvp(ctx):
    desafiado_id = ctx.author.id
    
    if desafiado_id not in DESAFIOS_PENDENTES:
        await ctx.send("❌ Você não tem nenhum pedido de PvP pendente!")
        return

    dados_desafio = DESAFIOS_PENDENTES.pop(desafiado_id)
    desafiante = dados_desafio["desafiante"]

    # Cria e armazena a nova partida
    partida = PartidaTCG(desafiante, ctx.author)
    PARTIDAS_ATIVAS[ctx.channel.id] = partida

    embed = discord.Embed(
        title="⚔️ DUELO INICIADO! ⚔️",
        description=f"{desafiante.mention} 🆚 {ctx.author.mention}\n\n"
                    f"☀️ Estação Inicial: **Dia** (Turno {partida.turno_global})\n"
                    f"🎲 Vez de jogar: {partida.turno_atual.mention}",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

@bot.command(name="rec")
async def recusar_pvp(ctx):
    desafiado_id = ctx.author.id
    
    if desafiado_id not in DESAFIOS_PENDENTES:
        await ctx.send("❌ Você não tem nenhum pedido de PvP pendente!")
        return

    dados_desafio = DESAFIOS_PENDENTES.pop(desafiado_id)
    desafiante = dados_desafio["desafiante"]

    await ctx.send(f"🚫 {ctx.author.mention} recusou o desafio de PvP de {desafiante.mention}.")

# -------------------------------------------------------------
# 4. COMANDO UNIFICADO DE JOGADA (!j)
# -------------------------------------------------------------
@bot.command(name="j")
async def executar_jogada(ctx, *args):
    canal_id = ctx.channel.id
    if canal_id not in PARTIDAS_ATIVAS:
        await ctx.send("❌ Não há nenhuma partida em andamento neste canal. Use `!pvp @jogador`!")
        return

    p = PARTIDAS_ATIVAS[canal_id]

    if ctx.author != p.turno_atual:
        await ctx.send(f"❌ Não é a sua vez! Vez de {p.turno_atual.mention}.", delete_after=5)
        return

    comando_texto = " ".join(args).upper()
    
    qtd_dados_atk = 1
    taxa_critico = 0
    multiplicador_critico = 1.0
    efeito = None
    passar_turno = False

    # Leitura das Flags do comando
    if "!ATK" in comando_texto:
        qtd_dados_atk = int(comando_texto.split("!ATK")[1].split()[0])
    if "!TAXACRIT" in comando_texto or "!TC" in comando_texto:
        tag = "!TAXACRIT" if "!TAXACRIT" in comando_texto else "!TC"
        taxa_critico = float(comando_texto.split(tag)[1].split()[0])
    if "!DANOCRIT" in comando_texto or "!DC" in comando_texto:
        tag = "!DANOCRIT" if "!DANOCRIT" in comando_texto else "!DC"
        val_str = comando_texto.split(tag)[1].split()[0].replace("X", "")
        multiplicador_critico = float(val_str)
    if "!EFF" in comando_texto:
        efeito = comando_texto.split("!EFF")[1].split()[0]
    if "!FIM" in comando_texto:
        passar_turno = True

    # Processamento de Dados e Crítico
    dados = [random.randint(1, 6) for _ in range(qtd_dados_atk)]
    dano_base = sum(dados)
    roll_critico = random.randint(1, 100)
    is_critico = roll_critico <= taxa_critico
    dano_final = int(dano_base * multiplicador_critico) if is_critico else dano_base

    # Incrementar Carga de Ativa por Atacar
    if p.turno_atual == p.j1:
        p.cargas_j1 = min(4, p.cargas_j1 + 1)
    else:
        p.cargas_j2 = min(4, p.cargas_j2 + 1)

    # Montagem do Log
    log = [f"🎲 **ATK ({qtd_dados_atk}d6):** {dados} ➔ Total: {dano_base}"]
    if taxa_critico > 0:
        if is_critico:
            log.append(f"⚡ **CRÍTICO!** ({roll_critico}% ≤ {taxa_critico}%) ➔ **Dano x{multiplicador_critico}: {dano_final}**")
        else:
            log.append(f"⚪ **Ataque Normal** ({roll_critico}% > {taxa_critico}%) ➔ Dano: {dano_final}")

    if efeito:
        log.append(f"✨ **Efeito do Turno:** {efeito}")

    if passar_turno:
        p.alternar_turno()
        log.append(f"🔄 **Turno Passado!** Próximo a jogar: {p.turno_atual.mention} (Estação: {p.estacao})")

    embed = discord.Embed(
        title=f"⚔️ Jogada de {ctx.author.display_name}",
        description="\n".join(log),
        color=discord.Color.gold() if is_critico else discord.Color.blue()
    )
    await ctx.send(embed=embed)

# -------------------------------------------------------------
# 5. COMANDOS DE PASSIVA, DANO E VITÓRIA (RANKING)
# -------------------------------------------------------------
@bot.command(name="dano")
async def aplicar_dano_direto(ctx, alvo: discord.Member, quantidade: int):
    canal_id = ctx.channel.id
    if canal_id not in PARTIDAS_ATIVAS:
        await ctx.send("❌ Nenhuma partida ativa neste canal.")
        return

    p = PARTIDAS_ATIVAS[canal_id]
    
    if alvo == p.j1:
        p.hp_j1 = max(0, p.hp_j1 - quantidade)
        hp_restante = p.hp_j1
    elif alvo == p.j2:
        p.hp_j2 = max(0, p.hp_j2 - quantidade)
        hp_restante = p.hp_j2
    else:
        await ctx.send("❌ Esse jogador não faz parte da partida!")
        return

    await ctx.send(f"🩸 {alvo.mention} sofreu **{quantidade} de Dano Directo**! (HP Restante: {hp_restante})")

    # Checar Derrota / Vitória
    if hp_restante <= 0:
        vencedor = p.j2 if alvo == p.j1 else p.j1
        await finalizar_partida(ctx, vencedor, alvo)

@bot.command(name="vitoria")
async def declarar_vitoria(ctx, perdedor: discord.Member):
    """Comando para encerrar a partida e enviar o resultado ao canal de ranking."""
    canal_id = ctx.channel.id
    if canal_id not in PARTIDAS_ATIVAS:
        await ctx.send("❌ Nenhuma partida ativa para encerrar.")
        return

    p = PARTIDAS_ATIVAS[canal_id]
    vencedor = ctx.author
    
    await finalizar_partida(ctx, vencedor, perdedor)

async def finalizar_partida(ctx, vencedor: discord.User, perdedor: discord.User):
    canal_id = ctx.channel.id
    
    # Atualiza Ranking na memória
    RANKING_JOGADORES.setdefault(vencedor.id, {"vitorias": 0, "derrotas": 0})
    RANKING_JOGADORES.setdefault(perdedor.id, {"vitorias": 0, "derrotas": 0})
    
    RANKING_JOGADORES[vencedor.id]["vitorias"] += 1
    RANKING_JOGADORES[perdedor.id]["derrotas"] += 1

    # Remove a partida ativa
    del PARTIDAS_ATIVAS[canal_id]

    await ctx.send(f"🏆 **PARTIDA ENCERRADA!** {vencedor.mention} venceu a batalha contra {perdedor.mention}!")

    # Notifica o canal de ranking do servidor
    canal_ranking = bot.get_channel(CANAL_RANKING_ID)
    if canal_ranking:
        embed = discord.Embed(title="📊 Placar de Partida Registrado", color=discord.Color.green())
        embed.add_field(name="🥇 Vencedor", value=f"{vencedor.mention} (+1 Vitória)", inline=True)
        embed.add_field(name="💀 Perdedor", value=f"{perdedor.mention} (+1 Derrota)", inline=True)
        await canal_ranking.send(embed=embed)

# -------------------------------------------------------------
# 6. EXECUÇÃO
# -------------------------------------------------------------
@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user.name} online e pronto para os duelos!")

bot.run("DISCORD-TOKEN")