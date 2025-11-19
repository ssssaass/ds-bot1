import discord
from discord.ext import commands
from discord import ui
import json
import os
from datetime import datetime

# ТОКЕН БОТА через переменную окружения
TOKEN = os.getenv("DISCORD_TOKEN")  # <- добавь переменную на Railway
if TOKEN is None:
    raise ValueError("❌ ERROR: Discord token not found in environment variables")

# Настройки бота
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Хранение данных
try:
    with open('ticket_data.json', 'r') as f:
        ticket_data = json.load(f)
except FileNotFoundError:
    ticket_data = {"ticket_count": 0, "active_tickets": {}}

def save_data():
    with open('ticket_data.json', 'w') as f:
        json.dump(ticket_data, f, indent=4)

# Класс для DropDown меню
class TicketDropdown(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="HWID Reset", description="Reset your HWID", emoji="🔄"),
            discord.SelectOption(label="Support", description="Get technical support", emoji="🔧"),
            discord.SelectOption(label="Purchase", description="Purchase related issues", emoji="💳")
        ]
        super().__init__(placeholder="Choose ticket type...", options=options, custom_id="ticket_dropdown")

    async def callback(self, interaction: discord.Interaction):
        await create_ticket(interaction, self.values[0])

class DropdownView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

# Класс для кнопки закрытия
class CloseButtonView(ui.View):
    def __init__(self, ticket_channel, ticket_number):
        super().__init__(timeout=None)
        self.ticket_channel = ticket_channel
        self.ticket_number = ticket_number

    @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        confirm_embed = discord.Embed(
            title="🔒 Close Ticket",
            description="Are you sure you want to close this ticket?",
            color=0xff0000
        )
        
        confirm_view = ui.View()
        confirm_button = ui.Button(label="Confirm Close", style=discord.ButtonStyle.danger)
        
        async def confirm_callback(interaction: discord.Interaction):
            # Создаем лог перед удалением
            guild = interaction.guild
            log_embed = discord.Embed(
                title=f"📁 Ticket #{self.ticket_number:04d} Closed",
                description=f"**Closed by:** {interaction.user.mention}\n**Closed at:** <t:{int(datetime.now().timestamp())}:f>",
                color=0xff0000
            )
            
            # Ищем канал для логов
            category = discord.utils.get(guild.categories, name="TICKETS")
            if category:
                log_channel = discord.utils.get(category.text_channels, name="ticket-logs")
                if not log_channel:
                    # Настройка прав для логов - только для роли поддержки
                    support_role = guild.get_role(1436675304289730632)
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    }
                    if support_role:
                        overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    
                    log_channel = await category.create_text_channel("ticket-logs", overwrites=overwrites)
                
                await log_channel.send(embed=log_embed)
            
            # Удаляем тикет из данных
            if str(self.ticket_channel.id) in ticket_data["active_tickets"]:
                del ticket_data["active_tickets"][str(self.ticket_channel.id)]
                save_data()
            
            await self.ticket_channel.delete()
        
        confirm_button.callback = confirm_callback
        confirm_view.add_item(confirm_button)
        
        await interaction.response.send_message(embed=confirm_embed, view=confirm_view, ephemeral=True)

# Функция создания тикета
async def create_ticket(interaction: discord.Interaction, ticket_type: str):
    ticket_data["ticket_count"] += 1
    ticket_number = ticket_data["ticket_count"]
    
    guild = interaction.guild
    
    # Получаем роль поддержки
    support_role = guild.get_role(1436675304289730632)
    
    # Ищем категорию TICKETS
    category = discord.utils.get(guild.categories, name="TICKETS")
    
    # Создаем категорию если нет
    if not category:
        # Настройка прав для категории - только для роли поддержки
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True, send_messages=True)
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
        
        # Создаем категорию В ВЕРХУ списка (position=0)
        category = await guild.create_category(
            name="TICKETS", 
            overwrites=overwrites,
            position=0  # Это поместит категорию в самый верх
        )
    
    # Создаем имя канала
    ticket_name = f"ticket-{ticket_number:04d}-{ticket_type.lower().replace(' ', '-')}"
    
    # Настройка прав доступа для тикета
    # Только автор тикета и роль поддержки имеют доступ
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),  # Все остальные не видят
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True, manage_channels=True)
    }
    
    # Добавляем права для роли поддержки
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(
            read_messages=True, 
            send_messages=True, 
            manage_messages=True,
            read_message_history=True
        )
    
    # Создаем канал тикета
    ticket_channel = await category.create_text_channel(
        name=ticket_name,
        overwrites=overwrites,
        topic=f"Ticket #{ticket_number:04d} | Type: {ticket_type} | Created by: {interaction.user.display_name}"
    )
    
    # Сохраняем данные тикета
    ticket_data["active_tickets"][str(ticket_channel.id)] = {
        "user_id": interaction.user.id,
        "ticket_number": ticket_number,
        "ticket_type": ticket_type,
        "created_at": datetime.now().isoformat()
    }
    save_data()
    
    # Создаем embed для тикета
    ticket_embed = discord.Embed(
        title=f"🎫 Ticket #{ticket_number:04d}",
        description="Thank you for contacting **Mented Support**!",
        color=0x5865F2
    )
    ticket_embed.add_field(
        name="📋 Ticket Information",
        value=f"**Type:** {ticket_type}\n**Created by:** {interaction.user.mention}\n**Created at:** <t:{int(datetime.now().timestamp())}:f>",
        inline=False
    )
    ticket_embed.add_field(
        name="📝 What to do next?",
        value="• Please describe your issue in detail\n• Provide any relevant information\n• Be patient while waiting for support\n• Use English or Russian languages",
        inline=False
    )
    ticket_embed.add_field(
        name="⚠️ Important Notes",
        value="Our support is only offered for problems caused by our Services. Tickets unrelated to Mented and our products will be closed.",
        inline=False
    )
    ticket_embed.set_footer(text="Mented Support Team")
    
    # Отправляем сообщения в тикет
    if support_role:
        ping_msg = await ticket_channel.send(f"{support_role.mention}")
    
    await ticket_channel.send(embed=ticket_embed, view=CloseButtonView(ticket_channel, ticket_number))
    
    # Подтверждение пользователю
    success_embed = discord.Embed(
        title="✅ Ticket Created Successfully!",
        description=f"Your ticket has been created: {ticket_channel.mention}\n\nOur support team will assist you shortly.",
        color=0x00ff00
    )
    await interaction.response.send_message(embed=success_embed, ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ {bot.user.name} is online!')
    print(f'📊 Connected to {len(bot.guilds)} server(s)')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Mented Tickets"))
    
    # Добавляем персистентное view
    bot.add_view(DropdownView())
    print("🎫 Ticket system ready!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """Создает сообщение с системой тикетов"""
    embed = discord.Embed(
        title="🎫 **Welcome to the Mented Ticket Support!**",
        color=0x5865F2
    )
    
    welcome_text = """**1.** Our support is only offered to you if there is a problem caused by our Services, tickets unrelated to Mented and our products will be closed.
**2.** Our main support language is English / Russian. Please use a translator if necessary.

👇 **Select your ticket type below:**"""
    
    embed.description = welcome_text
    embed.set_footer(text="We're here to help! • Mented Support")
    
    await ctx.send(embed=embed, view=DropdownView())
    await ctx.message.delete()

@bot.command()
@commands.has_permissions(administrator=True)
async def close(ctx):
    """Закрывает текущий тикет (админ команда)"""
    if "ticket" in ctx.channel.name.lower():
        # Находим данные тикета
        ticket_info = ticket_data["active_tickets"].get(str(ctx.channel.id))
        if ticket_info:
            ticket_number = ticket_info["ticket_number"]
            
            # Создаем лог
            log_embed = discord.Embed(
                title=f"📁 Ticket #{ticket_number:04d} Closed",
                description=f"**Closed by:** {ctx.author.mention}\n**Closed at:** <t:{int(datetime.now().timestamp())}:f>",
                color=0xff0000
            )
            
            # Ищем канал для логов
            category = discord.utils.get(ctx.guild.categories, name="TICKETS")
            if category:
                log_channel = discord.utils.get(category.text_channels, name="ticket-logs")
                if not log_channel:
                    # Настройка прав для логов - только для роли поддержки
                    support_role = ctx.guild.get_role(1436675304289730632)
                    overwrites = {
                        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    }
                    if support_role:
                        overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    
                    log_channel = await category.create_text_channel("ticket-logs", overwrites=overwrites)
                
                await log_channel.send(embed=log_embed)
            
            # Удаляем из данных и удаляем канал
            del ticket_data["active_tickets"][str(ctx.channel.id)]
            save_data()
            
            await ctx.send("🎫 Ticket closed successfully!")
            await ctx.channel.delete()
        else:
            await ctx.send("❌ Ticket data not found!")
    else:
        await ctx.send("❌ This is not a ticket channel!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command!")
    else:
        print(f"Error: {error}")

# Запуск бота
if __name__ == "__main__":
    print("🚀 Starting Mented Ticket Bot...")
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ ERROR: Invalid token! Check if the token is correct")
    except Exception as e:
        print(f"❌ ERROR: {e}")