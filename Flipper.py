import sys
import requests
import time
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout, QLineEdit, QComboBox, QAbstractItemView,
    QCheckBox, QTabWidget, QInputDialog
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor, QFont, QGuiApplication

# Your Hypixel API key
API_KEY = ''
BASE_URL = 'https://api.hypixel.net'
ITEMS_URL = 'https://api.hypixel.net/resources/skyblock/items'


class HypixelAuctionApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle('Hypixel Auction Scraper')
        self.setGeometry(100, 100, 1000, 600)  # Increased window size
        self.setStyleSheet("""
        QWidget {
            background-color: #f0f0f0;
            border-radius: 10px;
        }

        QLabel {
            color: #333;
            font-size: 14px;
        }

        QPushButton {
            background-color: #007aff;
            border: none;
            color: white;
            padding: 5px 10px;
            text-align: center;
            font-size: 14px;
            border-radius: 5px;
            margin: 4px 2px;
        }

        QPushButton:hover {
            background-color: #005bb5;
        }

        QLineEdit {
            border: 1px solid #ccc;
            border-radius: 5px;
            padding: 5px;
            font-size: 14px;
        }

        QTableWidget {
            border: 1px solid #ccc;
            border-radius: 5px;
            background-color: #fff;
        }
        """)

        self.watch_list = []
        self.npc_prices = self.fetch_npc_prices()

        layout = QVBoxLayout()

        self.initTitleBar(layout)

        self.info_label = QLabel('Click "Fetch Auctions" to get the nearest ending auctions.')
        layout.addWidget(self.info_label)

        button_layout = QHBoxLayout()

        self.fetch_button = QPushButton("Fetch")
        self.fetch_button.clicked.connect(self.fetch_auction_data)
        button_layout.addWidget(self.fetch_button)

        self.auto_fetch_checkbox = QCheckBox("Auto Fetch")
        self.auto_fetch_checkbox.stateChanged.connect(self.toggle_auto_fetch)
        button_layout.addWidget(self.auto_fetch_checkbox)

        self.add_watch_button = QPushButton('Add to Watch List')
        self.add_watch_button.clicked.connect(self.add_to_watch_list)
        button_layout.addWidget(self.add_watch_button)

        self.check_gaps_button = QPushButton('Check Price Gaps')
        self.check_gaps_button.clicked.connect(self.check_price_gaps)
        button_layout.addWidget(self.check_gaps_button)

        layout.addLayout(button_layout)

        self.filter_layout = QHBoxLayout()
        self.filter_label = QLabel('Filter by Item:')
        self.filter_layout.addWidget(self.filter_label)
        self.filter_input = QLineEdit()
        self.filter_layout.addWidget(self.filter_input)

        layout.addLayout(self.filter_layout)

        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.create_table_widget(), "All")
        layout.addWidget(self.tab_widget)

        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_countdowns)
        self.auto_fetch_timer = QTimer()
        self.auctions = []
        self.auctions_by_uuid = {}

        self.tab_widget.currentChanged.connect(self.update_countdowns)

    def create_table_widget(self, profit=False):
        table = QTableWidget()
        if profit:
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(['Item Name', 'Auction ID', 'Time Remaining', 'Profit'])
        else:
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(['Item Name', 'Auction ID', 'Time Remaining', 'Price Gap'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        return table

    def initTitleBar(self, layout):
        title_bar = QHBoxLayout()

        close_button = QPushButton('X')
        close_button.setFixedSize(20, 20)
        close_button.setStyleSheet("background-color: #ff5f57; border-radius: 10px;")
        close_button.clicked.connect(self.close)

        minimize_button = QPushButton('_')
        minimize_button.setFixedSize(20, 20)
        minimize_button.setStyleSheet("background-color: #ffbd2e; border-radius: 10px;")
        minimize_button.clicked.connect(self.showMinimized)

        maximize_button = QPushButton('□')
        maximize_button.setFixedSize(20, 20)
        maximize_button.setStyleSheet("background-color: #28c840; border-radius: 10px;")
        maximize_button.clicked.connect(self.showMaximized)

        title_bar.addWidget(close_button)
        title_bar.addWidget(minimize_button)
        title_bar.addWidget(maximize_button)
        title_bar.addStretch()

        layout.addLayout(title_bar)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(self.pos() + event.globalPos() - self.dragPos)
            self.dragPos = event.globalPos()
            event.accept()

    def fetch_npc_prices(self):
        response = requests.get(ITEMS_URL)
        if response.status_code == 200:
            items_data = response.json()
            npc_prices = {item['name'].lower(): item.get('npc_sell_price', 0) for item in items_data['items']}
            return npc_prices
        else:
            return {}

    def fetch_auction_data(self):
        auction_data = self.get_auction_data(page=0)
        if isinstance(auction_data, dict) and auction_data.get("success"):
            self.auctions = sorted(auction_data["auctions"], key=lambda x: x.get("end", 0))
            # empty auctions
            item_filter = self.filter_input.text().lower()

            # Only Bin Auctions
            self.auctions = [auction for auction in self.auctions if auction.get('bin')]
            auctions_by_uuid = {}
            for auction in self.auctions:
                auctions_by_uuid[auction['uuid']] = auction
            self.auctions_by_uuid = auctions_by_uuid
            filtered_auctions = self.auctions
            all_item_names = []
            profits_list = []
            lowest_list = []
            second_list = []
            bins = self.calculate_bins(filtered_auctions)
            for auction in filtered_auctions:
                if auction["item_name"].lower() not in all_item_names:
                    all_item_names.append(auction["item_name"].lower())
                    profit, lowest, second = self.calculate_price_gap(auction['item_name'], bins)
                    if profit is None:
                        continue
                    profits_list.append(profit)
                    lowest_list.append(lowest)
                    second_list.append(second)
            self.tab_widget.widget(0).setRowCount(len(profits_list))
            for i in range(0, len(profits_list)):
                auction_id_item = QTableWidgetItem(profits_list[i][1])
                auction_id_item.setToolTip(f'Click to copy /viewauction {profits_list[i][1]}')
                auction_id_item.setData(Qt.UserRole, profits_list[i][1])
                auction_id_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                font = QFont()
                font.setUnderline(True)
                auction_id_item.setFont(font)
                auction_id_item.setForeground(QColor('blue'))

                item_name_item = QTableWidgetItem(profits_list[i][0])
                if any(watch_item.lower() in profits_list[i][0].lower() for watch_item in self.watch_list):
                    item_name_item.setBackground(QColor(255, 255, 153))  # Highlight watched items

                price_gap = profits_list[i][3]

                self.tab_widget.widget(0).setItem(i, 0, item_name_item)
                self.tab_widget.widget(0).setItem(i, 1, auction_id_item)
                self.tab_widget.widget(0).setItem(i, 2, self.create_timer_item(profits_list[i][2]))
                self.tab_widget.widget(0).setItem(i, 3, QTableWidgetItem(f'{price_gap:,}' if price_gap is not None else 'N/A'))

            self.timer.start(1000)
        else:
            for i in range(4):
                self.tab_widget.widget(i).setRowCount(0)
            self.info_label.setText('Error fetching data.')

        self.update_countdowns()  # Ensure the countdowns are updated right after fetching data

    def calculate_bins(self, auctions):
        bins = {}
        for auction in auctions:
            if auction["bin"]:
                if auction["item_name"].lower() in bins:
                    bins[auction["item_name"].lower()].append(auction)
                else:
                    bins[auction["item_name"].lower()] = [auction]
        for key in bins:
            bins[key].sort(key=lambda x: x["starting_bid"])
        return bins


    def calculate_price_gap(self, item_name, bins):
        bins_for_item = bins[item_name.lower()]
        """Calculate the price gap for the given item name."""
        if len(bins_for_item) > 1:
            lowest_bin = bins_for_item[0]["starting_bid"]
            second_lowest_bin = bins_for_item[1]["starting_bid"]
            if lowest_bin < second_lowest_bin and second_lowest_bin - lowest_bin >= 1000:
                profit_list = [
                    item_name,
                    bins_for_item[0]["uuid"],
                    bins_for_item[0]["end"],
                    second_lowest_bin - lowest_bin
                ]
                lowest_item = [
                    item_name,
                    bins_for_item[0]["uuid"],
                    bins_for_item[0]["end"],
                    bins_for_item[0]["starting_bid"],
                    bins_for_item[0]['tier']
                ]
                second_item = [
                    item_name,
                    bins_for_item[1]["uuid"],
                    bins_for_item[1]["end"],
                    bins_for_item[1]["starting_bid"],
                    bins_for_item[1]['tier']
                ]
                return profit_list, lowest_item, second_item
        return None, None, None

    def populate_npc_price_table(self, table, auctions):
        profit_list = []
        for auction in auctions:
            item_name = auction["item_name"].lower()
            bin_price = auction.get("bin", 0)
            npc_price = self.npc_prices.get(item_name, 0)

            if npc_price > 0 and bin_price < npc_price:
                profit = npc_price - bin_price
                profit_list.append((item_name, auction["uuid"], auction["end"], profit))

        profit_list.sort(key=lambda x: x[3], reverse=True)  # Sort by profit

        table.setRowCount(len(profit_list))

        for i, (item_name, auction_id, end_time, profit) in enumerate(profit_list):
            item_name_item = QTableWidgetItem(item_name.capitalize())
            auction_id_item = QTableWidgetItem(auction_id)
            auction_id_item.setToolTip(f'Click to copy /viewauction {auction_id}')
            auction_id_item.setData(Qt.UserRole, auction_id)
            auction_id_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            auction_id_item.setForeground(QColor('blue'))

            table.setItem(i, 0, item_name_item)
            table.setItem(i, 1, auction_id_item)
            table.setItem(i, 2, self.create_timer_item(end_time))
            table.setItem(i, 3, QTableWidgetItem(f'{profit:,}'))

        table.cellClicked.connect(self.copy_auction_id_to_clipboard)

    def check_price_gaps(self):
        """Check the price gaps between the lowest and second lowest BINS."""
        item_name = self.filter_input.text().lower()
        filtered_bins = [auction for auction in self.auctions if
                         auction.get('bin') and item_name in auction["item_name"].lower()]

        if not filtered_bins:
            self.info_label.setText(f'No BINs found for {item_name}.')
            return

        filtered_bins.sort(key=lambda x: x["starting_bid"])

        if len(filtered_bins) > 1:
            lowest_bin = filtered_bins[0]["starting_bid"]
            second_lowest_bin = filtered_bins[1]["starting_bid"]
            gap = second_lowest_bin - lowest_bin

            # Display only if the lowest BIN is actually lower
            if lowest_bin < second_lowest_bin:
                self.info_label.setText(
                    f'Price gap for {item_name}: {gap:,} coins (Lowest: {lowest_bin:,}, Second Lowest: {second_lowest_bin:,})')
            else:
                self.info_label.setText(f'No significant price gap for {item_name}.')
        else:
            self.info_label.setText(f'Only one BIN found for {item_name}. No price gap to show.')

    def create_timer_item(self, end_time):
        time_remaining = self.get_time_remaining(end_time)
        timer_item = QTableWidgetItem(time_remaining)
        remaining_seconds = self.get_remaining_seconds(end_time)

        if remaining_seconds > 60:
            timer_item.setForeground(QColor('green'))
        elif 15 < remaining_seconds <= 60:
            timer_item.setForeground(QColor('orange'))
        else:
            timer_item.setForeground(QColor('red'))

        return timer_item

    def update_countdowns(self):
        current_time = time.time()
        current_tab = self.tab_widget.currentIndex()
        table = self.tab_widget.widget(current_tab)

        # Iterate over the rows in the current tab's table
        for i in range(table.rowCount()):
            # Retrieve the auction ID to ensure we get the correct auction
            auction_id_item = table.item(i, 1)
            auction_id = auction_id_item.data(Qt.UserRole)

            # Find the corresponding auction
            auction = self.auctions_by_uuid[auction_id]

            if auction:
                end_time = auction.get("end", 0)
                remaining_seconds = self.get_remaining_seconds(end_time)

                if remaining_seconds > 0:
                    timer_item = self.create_timer_item(end_time)
                    table.setItem(i, 2, timer_item)
                else:
                    table.setItem(i, 2, QTableWidgetItem("Ended"))

    def get_time_remaining(self, end_time):
        remaining_time = end_time / 1000 - time.time()
        if remaining_time > 0:
            minutes, seconds = divmod(int(remaining_time), 60)
            hours, minutes = divmod(minutes, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return "Ended"

    def get_remaining_seconds(self, end_time):
        return end_time / 1000 - time.time()

    def toggle_auto_fetch(self):
        if self.auto_fetch_checkbox.isChecked():
            self.auto_fetch_timer.start(30000)
            self.auto_fetch_timer.timeout.connect(self.fetch_auction_data)
        else:
            self.auto_fetch_timer.stop()

    def copy_auction_id_to_clipboard(self, row, column):
        table = self.tab_widget.currentWidget()
        auction_id_item = table.item(row, 1)
        auction_id = auction_id_item.data(Qt.UserRole)
        command = f'/viewauction {auction_id}'
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(command)
        self.info_label.setText(f'Copied to clipboard: {command}')

    def get_auction_data(self, page=0):
        data = requests.get("https://api.hypixel.net/skyblock/auctions").json()
        totalPages = data["totalPages"]
        all_pages_auctions = {'success': True, 'auctions': []}
        failed = 0

        for i in range(0, totalPages):
            url = f'https://api.hypixel.net/skyblock/auctions?page={i}'
            response = requests.get(url)
            if response.status_code == 200:
                value = json.loads(response.text)
                all_pages_auctions['auctions'].extend(value['auctions'])
                print(f'Obtained Page: {i}')
            else:
                failed += 1
                print(f'Failed Page: {i}')

        if failed == totalPages:
            all_pages_auctions['success'] = False

        return all_pages_auctions

    def add_to_watch_list(self):
        item_name, ok = QInputDialog.getText(self, 'Add to Watch List', 'Enter item name to watch:')
        if ok and item_name:
            self.watch_list.append(item_name)
            self.info_label.setText(f'Added "{item_name}" to watch list')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = HypixelAuctionApp()
    ex.show()
    sys.exit(app.exec_())