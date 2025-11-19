import discord
from discord.ext import commands
from discord import ui
import json
import os  # <- добавили
from datetime import datetime

# ТОКЕН БОТА через переменную окружения
TOKEN = os.getenv("DISCORD_TOKEN")
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

# Класс для кнопок покупки
class PurchaseButtons(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🛒 Purchase", style=discord.ButtonStyle.success, custom_id="purchase_button")
    async def purchase_button(self, interaction: discord.Interaction, button: ui.Button):
        await create_purchase_ticket(interaction, "Purchase")

    @ui.button(label="❓ Help with Purchase", style=discord.ButtonStyle.primary, custom_id="purchase_help_button")
    async def purchase_help_button(self, interaction: discord.Interaction, button: ui.Button):
        await create_purchase_ticket(interaction, "Purchase Help")

# Класс для кнопки закрытия тикета
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
                description=f"**Type:** Purchase\n**Closed by:** {interaction.user.mention}\n**Closed at:** <t:{int(datetime.now().timestamp())}:f>",
                color=0xff0000
            )
            
            # Ищем канал для логов
            category = discord.utils.get(guild.categories, name="TICKETS")
            if category:
                log_channel = discord.utils.get(category.text_channels, name="purchase-logs")
                if not log_channel:
                    # Настройка прав для логов - только для роли поддержки
                    support_role = guild.get_role(1436675304289730632)
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    }
                    if support_role:
                        overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    
                    log_channel = await category.create_text_channel("purchase-logs", overwrites=overwrites)
                
                await log_channel.send(embed=log_embed)
            
            # Удаляем тикет из данных
            if str(self.ticket_channel.id) in ticket_data["active_tickets"]:
                del ticket_data["active_tickets"][str(self.ticket_channel.id)]
                save_data()
            
            await self.ticket_channel.delete()
        
        confirm_button.callback = confirm_callback
        confirm_view.add_item(confirm_button)
        
        await interaction.response.send_message(embed=confirm_embed, view=confirm_view, ephemeral=True)

# Функция создания тикета покупки
async def create_purchase_ticket(interaction: discord.Interaction, ticket_type: str):
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
    if ticket_type == "Purchase":
        ticket_name = f"purchase-{ticket_number:04d}"
    else:
        ticket_name = f"purchase-help-{ticket_number:04d}"
    
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
    
    # Создаем embed для тикета покупки
    if ticket_type == "Purchase":
        ticket_embed = discord.Embed(
            title=f"🛒 Purchase Ticket #{ticket_number:04d}",
            description="Thank you for your interest in purchasing our products!",
            color=0x00ff00
        )
        ticket_embed.add_field(
            name="📋 Ticket Information",
            value=f"**Type:** {ticket_type}\n**Created by:** {interaction.user.mention}\n**Created at:** <t:{int(datetime.now().timestamp())}:f>",
            inline=False
        )
        ticket_embed.add_field(
            name="💰 What to do next?",
            value="• Please specify what product you want to purchase\n• Let us know your preferred payment method\n• Our sales team will assist you with the purchase process",
            inline=False
        )
    else:
        ticket_embed = discord.Embed(
            title=f"❓ Purchase Help Ticket #{ticket_number:04d}",
            description="Thank you for contacting us about purchase assistance!",
            color=0x0099ff
        )
        ticket_embed.add_field(
            name="📋 Ticket Information",
            value=f"**Type:** {ticket_type}\n**Created by:** {interaction.user.mention}\n**Created at:** <t:{int(datetime.now().timestamp())}:f>",
            inline=False
        )
        ticket_embed.add_field(
            name="💡 How can we help?",
            value="• Please describe what you need help with\n• Specify any issues you're having with the purchase process\n• Our team will guide you through everything",
            inline=False
        )
    
    ticket_embed.add_field(
        name="⏰ Response Time",
        value="Our team will respond as soon as possible. Please be patient.",
        inline=False
    )
    ticket_embed.set_footer(text="Mented Sales Team")
    
    # Отправляем сообщения в тикет
    if support_role:
        ping_msg = await ticket_channel.send(f"{support_role.mention}")
    
    await ticket_channel.send(embed=ticket_embed, view=CloseButtonView(ticket_channel, ticket_number))
    
    # Подтверждение пользователю
    success_embed = discord.Embed(
        title="✅ Ticket Created Successfully!",
        description=f"Your {ticket_type.lower()} ticket has been created: {ticket_channel.mention}\n\nOur sales team will assist you shortly.",
        color=0x00ff00
    )
    await interaction.response.send_message(embed=success_embed, ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ {bot.user.name} is online!')
    print(f'📊 Connected to {len(bot.guilds)} server(s)')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Mented Tickets"))
    
    # Добавляем персистентное view для кнопок покупки
    bot.add_view(PurchaseButtons())
    print("🎫 Purchase ticket system ready!")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_purchase(ctx):
    """Создает сообщение с системой тикетов покупки в текущем канале"""
    embed = discord.Embed(
        title="🛒 **Mented Purchase Support**",
        description="Welcome to our purchase department! We're here to help you with:\n\n• **Product Purchases** - Buy our products securely\n• **Purchase Assistance** - Get help with buying process\n• **Payment Issues** - Resolve any payment problems\n\n👇 **Choose an option below:**",
        color=0x00ff00
    )
    
    embed.add_field(
        name="🛒 Purchase",
        value="Start a new purchase order for our products",
        inline=True
    )
    embed.add_field(
        name="❓ Help with Purchase",
        value="Get assistance with the purchase process",
        inline=True
    )
    
    embed.add_field(
        name="ℹ️ Information",
        value="• Our support team will assist you shortly\n• Please be patient for responses\n• Use English or Russian languages",
        inline=False
    )
    
    embed.set_footer(text="Mented Sales • Fast and Secure Purchases")
    
    await ctx.send(embed=embed, view=PurchaseButtons())
    await ctx.message.delete()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_purchase_channel(ctx):
    """Создает сообщение с системой тикетов покупки в указанном канале"""
    try:
        # Получаем целевой канал по ID
        target_channel_id = 1436673657165320192
        target_channel = bot.get_channel(target_channel_id)
        
        if target_channel is None:
            await ctx.send("❌ Target channel not found!")
            return
        
        embed = discord.Embed(
            title="🛒 **Mented Purchase Support**",
            description="Welcome to our purchase department! We're here to help you with:\n\n• **Product Purchases** - Buy our products securely\n• **Purchase Assistance** - Get help with buying process\n• **Payment Issues** - Resolve any payment problems\n\n👇 **Choose an option below:**",
            color=0x00ff00
        )
        
        embed.add_field(
            name="🛒 Purchase",
            value="Start a new purchase order for our products",
            inline=True
        )
        embed.add_field(
            name="❓ Help with Purchase",
            value="Get assistance with the purchase process",
            inline=True
        )
        
        embed.add_field(
            name="ℹ️ Information",
            value="• Our support team will assist you shortly\n• Please be patient for responses\n• Use English or Russian languages",
            inline=False
        )
        
        embed.set_footer(text="Mented Sales • Fast and Secure Purchases")
        
        await target_channel.send(embed=embed, view=PurchaseButtons())
        await ctx.send("✅ Purchase ticket system setup completed!")
        
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def close(ctx):
    """Закрывает текущий тикет (админ команда)"""
    if "purchase" in ctx.channel.name.lower():
        # Находим данные тикета
        ticket_info = ticket_data["active_tickets"].get(str(ctx.channel.id))
        if ticket_info:
            ticket_number = ticket_info["ticket_number"]
            ticket_type = ticket_info["ticket_type"]
            
            # Создаем лог
            log_embed = discord.Embed(
                title=f"📁 Ticket #{ticket_number:04d} Closed",
                description=f"**Type:** {ticket_type}\n**Closed by:** {ctx.author.mention}\n**Closed at:** <t:{int(datetime.now().timestamp())}:f>",
                color=0xff0000
            )
            
            # Ищем канал для логов
            category = discord.utils.get(ctx.guild.categories, name="TICKETS")
            if category:
                log_channel = discord.utils.get(category.text_channels, name="purchase-logs")
                if not log_channel:
                    # Настройка прав для логов - только для роли поддержки
                    support_role = ctx.guild.get_role(1436675304289730632)
                    overwrites = {
                        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    }
                    if support_role:
                        overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    
                    log_channel = await category.create_text_channel("purchase-logs", overwrites=overwrites)
                
                await log_channel.send(embed=log_embed)
            
            # Удаляем из данных и удаляем канал
            del ticket_data["active_tickets"][str(ctx.channel.id)]
            save_data()
            
            await ctx.send("🎫 Ticket closed successfully!")
            await ctx.channel.delete()
        else:
            await ctx.send("❌ Ticket data not found!")
    else:
        await ctx.send("❌ This is not a purchase ticket channel!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command!")
    else:
        print(f"Error: {error}")

# Запуск бота
if __name__ == "__main__":
    print("🚀 Starting Mented Purchase Ticket Bot...")
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ ERROR: Invalid token! Check if the token is correct")
    except Exception as e:
        print(f"❌ ERROR: {e}")