import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
from typing import Optional
from flask import Flask
from threading import Thread

# Flask app to keep bot alive
app = Flask('')

@app.route('/')
def home():
    return "✅ Dropshipping Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Data storage
DATA_FILE = 'bot_data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        'products': {},
        'orders': {},
        'suppliers': {},
        'settings': {
            'order_channel': None,
            'notification_channel': None,
            'currency': 'USD'
        }
    }

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

data = load_data()

# Product Management
class ProductModal(discord.ui.Modal, title='Add Product'):
    name = discord.ui.TextInput(
        label='Product Name',
        placeholder='Enter product name...',
        required=True
    )
    
    description = discord.ui.TextInput(
        label='Description',
        style=discord.TextStyle.paragraph,
        placeholder='Enter product description...',
        required=True,
        max_length=1000
    )
    
    price = discord.ui.TextInput(
        label='Price',
        placeholder='19.99',
        required=True
    )
    
    supplier_cost = discord.ui.TextInput(
        label='Supplier Cost',
        placeholder='9.99',
        required=True
    )
    
    stock = discord.ui.TextInput(
        label='Stock Quantity',
        placeholder='100',
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        product_id = str(len(data['products']) + 1)
        
        try:
            price_val = float(self.price.value)
            cost_val = float(self.supplier_cost.value)
            stock_val = int(self.stock.value)
            profit = price_val - cost_val
            margin = (profit / price_val * 100) if price_val > 0 else 0
            
            data['products'][product_id] = {
                'name': self.name.value,
                'description': self.description.value,
                'price': price_val,
                'supplier_cost': cost_val,
                'stock': stock_val,
                'profit_margin': round(margin, 2),
                'created_at': datetime.now().isoformat(),
                'active': True
            }
            
            save_data(data)
            
            embed = discord.Embed(
                title="✅ Product Added Successfully",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Product ID", value=product_id, inline=True)
            embed.add_field(name="Name", value=self.name.value, inline=True)
            embed.add_field(name="Price", value=f"${price_val:.2f}", inline=True)
            embed.add_field(name="Cost", value=f"${cost_val:.2f}", inline=True)
            embed.add_field(name="Profit", value=f"${profit:.2f}", inline=True)
            embed.add_field(name="Margin", value=f"{margin:.1f}%", inline=True)
            embed.add_field(name="Stock", value=str(stock_val), inline=True)
            
            await interaction.response.send_message(embed=embed)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid input! Please enter valid numbers for price, cost, and stock.",
                ephemeral=True
            )

class OrderModal(discord.ui.Modal, title='Create Order'):
    product_id = discord.ui.TextInput(
        label='Product ID',
        placeholder='Enter product ID...',
        required=True
    )
    
    quantity = discord.ui.TextInput(
        label='Quantity',
        placeholder='1',
        required=True
    )
    
    customer_name = discord.ui.TextInput(
        label='Customer Name',
        placeholder='John Doe',
        required=True
    )
    
    customer_email = discord.ui.TextInput(
        label='Customer Email',
        placeholder='customer@email.com',
        required=True
    )
    
    shipping_address = discord.ui.TextInput(
        label='Shipping Address',
        style=discord.TextStyle.paragraph,
        placeholder='123 Main St, City, State, ZIP',
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        product_id = self.product_id.value
        
        if product_id not in data['products']:
            await interaction.response.send_message(
                f"❌ Product ID {product_id} not found!",
                ephemeral=True
            )
            return
        
        product = data['products'][product_id]
        
        try:
            qty = int(self.quantity.value)
            
            if qty > product['stock']:
                await interaction.response.send_message(
                    f"❌ Insufficient stock! Available: {product['stock']}",
                    ephemeral=True
                )
                return
            
            order_id = f"ORD-{len(data['orders']) + 1:04d}"
            total = product['price'] * qty
            profit = (product['price'] - product['supplier_cost']) * qty
            
            data['orders'][order_id] = {
                'product_id': product_id,
                'product_name': product['name'],
                'quantity': qty,
                'total': total,
                'profit': profit,
                'customer_name': self.customer_name.value,
                'customer_email': self.customer_email.value,
                'shipping_address': self.shipping_address.value,
                'status': 'pending',
                'created_at': datetime.now().isoformat(),
                'created_by': str(interaction.user.id)
            }
            
            # Update stock
            data['products'][product_id]['stock'] -= qty
            save_data(data)
            
            # Create order confirmation embed
            embed = discord.Embed(
                title="🛒 New Order Created",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Order ID", value=order_id, inline=True)
            embed.add_field(name="Status", value="⏳ Pending", inline=True)
            embed.add_field(name="Product", value=product['name'], inline=False)
            embed.add_field(name="Quantity", value=str(qty), inline=True)
            embed.add_field(name="Total", value=f"${total:.2f}", inline=True)
            embed.add_field(name="Profit", value=f"${profit:.2f}", inline=True)
            embed.add_field(name="Customer", value=self.customer_name.value, inline=True)
            embed.add_field(name="Email", value=self.customer_email.value, inline=True)
            embed.add_field(name="Shipping Address", value=self.shipping_address.value, inline=False)
            embed.set_footer(text=f"Created by {interaction.user.name}")
            
            await interaction.response.send_message(embed=embed)
            
            # Send to order channel if configured
            if data['settings']['order_channel']:
                channel = bot.get_channel(data['settings']['order_channel'])
                if channel:
                    await channel.send(embed=embed)
                    
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid quantity! Please enter a valid number.",
                ephemeral=True
            )

# Slash Commands
@bot.tree.command(name="addproduct", description="Add a new product to the catalog")
@app_commands.checks.has_permissions(manage_messages=True)
async def add_product(interaction: discord.Interaction):
    await interaction.response.send_modal(ProductModal())

@bot.tree.command(name="products", description="View all products")
async def list_products(interaction: discord.Interaction):
    if not data['products']:
        await interaction.response.send_message("📦 No products available yet!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📦 Product Catalog",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    for pid, product in data['products'].items():
        status = "✅ Active" if product.get('active', True) else "❌ Inactive"
        value = (
            f"**Price:** ${product['price']:.2f} | **Cost:** ${product['supplier_cost']:.2f}\n"
            f"**Profit:** ${product['price'] - product['supplier_cost']:.2f} | "
            f"**Margin:** {product['profit_margin']:.1f}%\n"
            f"**Stock:** {product['stock']} | **Status:** {status}"
        )
        embed.add_field(
            name=f"ID: {pid} - {product['name']}",
            value=value,
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="product", description="View detailed product information")
@app_commands.describe(product_id="The product ID to view")
async def view_product(interaction: discord.Interaction, product_id: str):
    if product_id not in data['products']:
        await interaction.response.send_message(f"❌ Product ID {product_id} not found!", ephemeral=True)
        return
    
    product = data['products'][product_id]
    profit = product['price'] - product['supplier_cost']
    
    embed = discord.Embed(
        title=f"📦 {product['name']}",
        description=product['description'],
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Product ID", value=product_id, inline=True)
    embed.add_field(name="Price", value=f"${product['price']:.2f}", inline=True)
    embed.add_field(name="Supplier Cost", value=f"${product['supplier_cost']:.2f}", inline=True)
    embed.add_field(name="Profit per Unit", value=f"${profit:.2f}", inline=True)
    embed.add_field(name="Profit Margin", value=f"{product['profit_margin']:.1f}%", inline=True)
    embed.add_field(name="Stock", value=str(product['stock']), inline=True)
    embed.add_field(name="Status", value="✅ Active" if product.get('active', True) else "❌ Inactive", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="createorder", description="Create a new customer order")
@app_commands.checks.has_permissions(manage_messages=True)
async def create_order(interaction: discord.Interaction):
    await interaction.response.send_modal(OrderModal())

@bot.tree.command(name="orders", description="View all orders")
async def list_orders(interaction: discord.Interaction):
    if not data['orders']:
        await interaction.response.send_message("📋 No orders yet!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📋 Order List",
        color=discord.Color.purple(),
        timestamp=datetime.now()
    )
    
    status_emoji = {
        'pending': '⏳',
        'processing': '🔄',
        'shipped': '📦',
        'delivered': '✅',
        'cancelled': '❌'
    }
    
    for oid, order in list(data['orders'].items())[-10:]:
        status = status_emoji.get(order['status'], '❓')
        value = (
            f"**Product:** {order['product_name']}\n"
            f"**Quantity:** {order['quantity']} | **Total:** ${order['total']:.2f}\n"
            f"**Profit:** ${order['profit']:.2f} | **Status:** {status} {order['status'].title()}\n"
            f"**Customer:** {order['customer_name']}"
        )
        embed.add_field(name=oid, value=value, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="order", description="View detailed order information")
@app_commands.describe(order_id="The order ID to view")
async def view_order(interaction: discord.Interaction, order_id: str):
    if order_id not in data['orders']:
        await interaction.response.send_message(f"❌ Order {order_id} not found!", ephemeral=True)
        return
    
    order = data['orders'][order_id]
    
    status_emoji = {
        'pending': '⏳',
        'processing': '🔄',
        'shipped': '📦',
        'delivered': '✅',
        'cancelled': '❌'
    }
    
    embed = discord.Embed(
        title=f"📋 Order {order_id}",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Status", value=f"{status_emoji.get(order['status'], '❓')} {order['status'].title()}", inline=True)
    embed.add_field(name="Product", value=order['product_name'], inline=True)
    embed.add_field(name="Quantity", value=str(order['quantity']), inline=True)
    embed.add_field(name="Total", value=f"${order['total']:.2f}", inline=True)
    embed.add_field(name="Profit", value=f"${order['profit']:.2f}", inline=True)
    embed.add_field(name="Customer", value=order['customer_name'], inline=False)
    embed.add_field(name="Email", value=order['customer_email'], inline=True)
    embed.add_field(name="Shipping Address", value=order['shipping_address'], inline=False)
    embed.add_field(name="Created", value=order['created_at'][:10], inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="updatestatus", description="Update order status")
@app_commands.describe(
    order_id="The order ID to update",
    status="New status"
)
@app_commands.choices(status=[
    app_commands.Choice(name="Pending", value="pending"),
    app_commands.Choice(name="Processing", value="processing"),
    app_commands.Choice(name="Shipped", value="shipped"),
    app_commands.Choice(name="Delivered", value="delivered"),
    app_commands.Choice(name="Cancelled", value="cancelled")
])
@app_commands.checks.has_permissions(manage_messages=True)
async def update_status(interaction: discord.Interaction, order_id: str, status: str):
    if order_id not in data['orders']:
        await interaction.response.send_message(f"❌ Order {order_id} not found!", ephemeral=True)
        return
    
    old_status = data['orders'][order_id]['status']
    data['orders'][order_id]['status'] = status
    save_data(data)
    
    embed = discord.Embed(
        title="✅ Order Status Updated",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Order ID", value=order_id, inline=True)
    embed.add_field(name="Old Status", value=old_status.title(), inline=True)
    embed.add_field(name="New Status", value=status.title(), inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="updatestock", description="Update product stock")
@app_commands.describe(
    product_id="Product ID",
    quantity="New stock quantity"
)
@app_commands.checks.has_permissions(manage_messages=True)
async def update_stock(interaction: discord.Interaction, product_id: str, quantity: int):
    if product_id not in data['products']:
        await interaction.response.send_message(f"❌ Product ID {product_id} not found!", ephemeral=True)
        return
    
    old_stock = data['products'][product_id]['stock']
    data['products'][product_id]['stock'] = quantity
    save_data(data)
    
    embed = discord.Embed(
        title="✅ Stock Updated",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Product", value=data['products'][product_id]['name'], inline=False)
    embed.add_field(name="Old Stock", value=str(old_stock), inline=True)
    embed.add_field(name="New Stock", value=str(quantity), inline=True)
    embed.add_field(name="Change", value=f"{quantity - old_stock:+d}", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stats", description="View business statistics")
async def stats(interaction: discord.Interaction):
    total_products = len(data['products'])
    total_orders = len(data['orders'])
    
    total_revenue = sum(order['total'] for order in data['orders'].values())
    total_profit = sum(order['profit'] for order in data['orders'].values())
    
    pending_orders = sum(1 for order in data['orders'].values() if order['status'] == 'pending')
    completed_orders = sum(1 for order in data['orders'].values() if order['status'] == 'delivered')
    
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
    avg_profit_per_order = total_profit / total_orders if total_orders > 0 else 0
    
    embed = discord.Embed(
        title="📊 Business Statistics",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    embed.add_field(name="Total Products", value=str(total_products), inline=True)
    embed.add_field(name="Total Orders", value=str(total_orders), inline=True)
    embed.add_field(name="Pending Orders", value=str(pending_orders), inline=True)
    embed.add_field(name="Total Revenue", value=f"${total_revenue:.2f}", inline=True)
    embed.add_field(name="Total Profit", value=f"${total_profit:.2f}", inline=True)
    embed.add_field(name="Completed Orders", value=str(completed_orders), inline=True)
    embed.add_field(name="Avg Order Value", value=f"${avg_order_value:.2f}", inline=True)
    embed.add_field(name="Avg Profit/Order", value=f"${avg_profit_per_order:.2f}", inline=True)
    
    if total_revenue > 0:
        profit_margin = (total_profit / total_revenue) * 100
        embed.add_field(name="Overall Margin", value=f"{profit_margin:.1f}%", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="deleteproduct", description="Delete a product")
@app_commands.describe(product_id="Product ID to delete")
@app_commands.checks.has_permissions(administrator=True)
async def delete_product(interaction: discord.Interaction, product_id: str):
    if product_id not in data['products']:
        await interaction.response.send_message(f"❌ Product ID {product_id} not found!", ephemeral=True)
        return
    
    product_name = data['products'][product_id]['name']
    del data['products'][product_id]
    save_data(data)
    
    await interaction.response.send_message(
        f"✅ Product **{product_name}** (ID: {product_id}) has been deleted.",
        ephemeral=True
    )

@bot.tree.command(name="help", description="View all available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Dropshipping Bot Commands",
        description="Complete list of available commands",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📦 Product Management",
        value=(
            "`/addproduct` - Add a new product\n"
            "`/products` - View all products\n"
            "`/product <id>` - View product details\n"
            "`/updatestock <id> <qty>` - Update stock\n"
            "`/deleteproduct <id>` - Delete a product"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📋 Order Management",
        value=(
            "`/createorder` - Create new order\n"
            "`/orders` - View all orders\n"
            "`/order <id>` - View order details\n"
            "`/updatestatus <id> <status>` - Update order status"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📊 Analytics",
        value=(
            "`/stats` - View business statistics"
        ),
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Other",
        value=(
            "`/help` - Show this help message"
        ),
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'✅ {bot.user} is now online!')
    print(f'📡 Connected to {len(bot.guilds)} servers')
    print('🛒 Bot is ready to manage your dropshipping business!')
    print('🌐 Web server running on port 8080')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command!")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"Error: {error}")

# Run the bot
if __name__ == "__main__":
    print("🚀 Starting Dropshipping Bot...")
    print("🔄 Starting keep-alive web server...")
    
    keep_alive()
    
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("\n❌ ERROR: DISCORD_BOT_TOKEN not found!")
        print("Please add it in the Secrets tab (🔒 icon)")
        exit(1)
    
    print("✅ Token found! Starting bot...")
    bot.run(token)
