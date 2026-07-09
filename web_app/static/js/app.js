/**
 * 米游社商品兑换助手 - 网页版前端逻辑
 * Author: Jyf0214
 */

// ─── 全局状态 ────────────────────────────────────────────────────────────────

let currentGameKey = '';
let currentGoods = [];
let wishlistData = [];
let qrCheckTimer = null;

// ─── SocketIO 连接 ──────────────────────────────────────────────────────────

const socket = io();

socket.on('connect', function () {
    console.log('WebSocket 已连接');
});

socket.on('disconnect', function () {
    console.log('WebSocket 已断开');
});

socket.on('task_log', function (data) {
    const logView = document.getElementById('logView');
    if (logView) {
        const time = new Date().toLocaleTimeString();
        logView.textContent += `[${data.task}] ${data.message}\n`;
        logView.scrollTop = logView.scrollHeight;
    }
});

socket.on('task_completed', function (data) {
    showToast(`任务 "${data.task}" 执行完成`, 'success');
    loadTasks();
});

// ─── 工具函数 ────────────────────────────────────────────────────────────────

function showToast(message, type) {
    type = type || 'info';
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function () {
        toast.remove();
    }, 3000);
}

function apiRequest(url, options) {
    options = options || {};
    var method = options.method || 'GET';
    var body = options.body;

    var fetchOptions = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
    };

    if (body) {
        fetchOptions.body = JSON.stringify(body);
    }

    return fetch(url, fetchOptions)
        .then(function (response) {
            return response.json();
        })
        .catch(function (error) {
            console.error('请求失败:', error);
            showToast('网络请求失败', 'error');
            return { success: false, message: '网络请求失败' };
        });
}

// ─── 标签页切换 ──────────────────────────────────────────────────────────────

document.querySelectorAll('.tab-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
        if (this.disabled) return;

        document.querySelectorAll('.tab-btn').forEach(function (b) {
            b.classList.remove('active');
        });
        document.querySelectorAll('.tab-panel').forEach(function (p) {
            p.classList.remove('active');
        });

        this.classList.add('active');
        var tabId = 'tab-' + this.getAttribute('data-tab');
        document.getElementById(tabId).classList.add('active');
    });
});

// ─── 登录标签页切换 ──────────────────────────────────────────────────────────

document.querySelectorAll('.login-tab-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
        document.querySelectorAll('.login-tab-btn').forEach(function (b) {
            b.classList.remove('active');
        });
        document.querySelectorAll('.login-panel').forEach(function (p) {
            p.classList.remove('active');
        });

        this.classList.add('active');
        var panelId = 'login-' + this.getAttribute('data-login-tab');
        document.getElementById(panelId).classList.add('active');
    });
});

// ─── 登录相关 ────────────────────────────────────────────────────────────────

function checkLoginStatus() {
    apiRequest('/api/login/status').then(function (data) {
        if (data.logged_in) {
            setLoggedIn(data.account_id);
        } else {
            setLoggedOut();
        }
    });
}

function setLoggedIn(accountId) {
    var statusBar = document.getElementById('statusBar');
    var statusText = document.getElementById('statusText');
    statusBar.className = 'status-bar status-success';
    statusText.textContent = '已登录 - 账号ID: ' + accountId;

    document.querySelectorAll('.tab-btn[data-tab="goods"], .tab-btn[data-tab="tasks"]').forEach(function (btn) {
        btn.disabled = false;
    });
}

function setLoggedOut() {
    var statusBar = document.getElementById('statusBar');
    var statusText = document.getElementById('statusText');
    statusBar.className = 'status-bar status-error';
    statusText.textContent = '未登录 - 请先登录';

    document.querySelectorAll('.tab-btn[data-tab="goods"], .tab-btn[data-tab="tasks"]').forEach(function (btn) {
        btn.disabled = true;
    });
}

function generateQR() {
    var btn = document.getElementById('generateQrBtn');
    btn.disabled = true;
    btn.textContent = '生成中...';

    apiRequest('/api/login/qr/generate', { method: 'POST' }).then(function (data) {
        if (data.success) {
            var qrImage = document.getElementById('qrImage');
            var qrPlaceholder = document.getElementById('qrPlaceholder');
            qrImage.src = data.qr_image;
            qrImage.style.display = 'block';
            qrPlaceholder.style.display = 'none';

            btn.textContent = '等待扫码...';
            document.getElementById('qrStatus').textContent = '请使用米游社 App 扫描二维码';

            // 开始轮询检查登录状态
            startQRCheck(data.ticket);
        } else {
            showToast('生成二维码失败', 'error');
            btn.disabled = false;
            btn.textContent = '生成二维码';
        }
    });
}

function startQRCheck(ticket) {
    if (qrCheckTimer) {
        clearInterval(qrCheckTimer);
    }

    qrCheckTimer = setInterval(function () {
        apiRequest('/api/login/qr/check', {
            method: 'POST',
            body: { ticket: ticket },
        }).then(function (data) {
            if (data.status === 'success') {
                clearInterval(qrCheckTimer);
                qrCheckTimer = null;
                showToast('登录成功！', 'success');
                document.getElementById('qrStatus').textContent = '登录成功！';
                document.getElementById('generateQrBtn').disabled = false;
                document.getElementById('generateQrBtn').textContent = '生成二维码';
                checkLoginStatus();
                // 切换到商品页
                switchTab('goods');
            } else if (data.status === 'error') {
                clearInterval(qrCheckTimer);
                qrCheckTimer = null;
                showToast('登录失败: ' + data.message, 'error');
                document.getElementById('qrStatus').textContent = '';
                document.getElementById('generateQrBtn').disabled = false;
                document.getElementById('generateQrBtn').textContent = '生成二维码';
            } else {
                document.getElementById('qrStatus').textContent = data.message || '等待扫码...';
            }
        });
    }, 2000);
}

function manualLogin() {
    var cookieStr = document.getElementById('cookieInput').value.trim();
    if (!cookieStr) {
        showToast('请输入 Cookie', 'error');
        return;
    }

    apiRequest('/api/login/manual', {
        method: 'POST',
        body: { cookie: cookieStr },
    }).then(function (data) {
        if (data.success) {
            showToast('登录成功！', 'success');
            checkLoginStatus();
            switchTab('goods');
        } else {
            showToast(data.message || '登录失败', 'error');
        }
    });
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(function (btn) {
        if (btn.getAttribute('data-tab') === tabName && !btn.disabled) {
            btn.click();
        }
    });
}

// ─── 商品相关 ────────────────────────────────────────────────────────────────

function loadGames() {
    apiRequest('/api/games').then(function (data) {
        if (data.success) {
            var select = document.getElementById('gameSelect');
            select.innerHTML = '';
            data.games.forEach(function (game) {
                var option = document.createElement('option');
                option.value = game.key;
                option.textContent = game.name;
                select.appendChild(option);
            });
            if (data.games.length > 0) {
                currentGameKey = data.games[0].key;
                loadGoods();
            }
        }
    });
}

function loadGoods() {
    var gameKey = document.getElementById('gameSelect').value;
    if (!gameKey) return;
    currentGameKey = gameKey;

    var tbody = document.getElementById('goodsBody');
    tbody.innerHTML = '<tr><td colspan="5" class="empty-row">加载中...</td></tr>';

    // 加载米游币
    apiRequest('/api/points').then(function (data) {
        if (data.success) {
            document.getElementById('pointsLabel').textContent = '米游币: ' + data.points;
        }
    });

    // 加载商品
    apiRequest('/api/goods/' + encodeURIComponent(gameKey)).then(function (data) {
        if (data.success) {
            currentGoods = data.goods;
            displayGoods(data.goods);
        } else {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-row">' + (data.message || '加载失败') + '</td></tr>';
        }
    });
}

function displayGoods(goods) {
    var tbody = document.getElementById('goodsBody');
    tbody.innerHTML = '';

    if (!goods || goods.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-row">暂无商品</td></tr>';
        return;
    }

    goods.forEach(function (item, index) {
        var tr = document.createElement('tr');

        // 图标
        var tdIcon = document.createElement('td');
        var iconDiv = document.createElement('div');
        iconDiv.className = 'goods-icon';
        if (item.icon) {
            var img = document.createElement('img');
            img.src = item.icon;
            img.alt = item.name;
            img.loading = 'lazy';
            img.onerror = function () {
                this.parentElement.innerHTML = '<span class="placeholder">无图</span>';
            };
            iconDiv.appendChild(img);
        } else {
            iconDiv.innerHTML = '<span class="placeholder">无图</span>';
        }
        tdIcon.appendChild(iconDiv);
        tr.appendChild(tdIcon);

        // 商品名称
        var tdName = document.createElement('td');
        tdName.className = 'goods-name';
        tdName.textContent = item.name || '';
        tr.appendChild(tdName);

        // 价格
        var tdPrice = document.createElement('td');
        tdPrice.className = 'goods-price';
        tdPrice.textContent = (item.price || 0) + ' 币';
        tr.appendChild(tdPrice);

        // 兑换时间
        var tdTime = document.createElement('td');
        tdTime.className = 'goods-time';
        tdTime.textContent = item.time || '未知';
        tr.appendChild(tdTime);

        // 操作
        var tdAction = document.createElement('td');
        var addBtn = document.createElement('button');
        addBtn.className = 'btn btn-primary btn-sm';
        addBtn.textContent = '加入心愿单';
        addBtn.onclick = function () {
            addToWishlist(item);
        };
        tdAction.appendChild(addBtn);
        tr.appendChild(tdAction);

        tbody.appendChild(tr);
    });
}

function addToWishlist(item) {
    apiRequest('/api/wishlist', {
        method: 'POST',
        body: {
            name: item.name,
            id: item.id,
            time: item.time,
            biz: item.biz || currentGameKey,
        },
    }).then(function (data) {
        if (data.success) {
            showToast(data.message, 'success');
        } else {
            showToast(data.message || '添加失败', 'error');
        }
    });
}

function clearWishlist() {
    if (!confirm('确定要清空心愿单吗？')) return;

    apiRequest('/api/wishlist', { method: 'DELETE' }).then(function (data) {
        if (data.success) {
            showToast('心愿单已清空', 'success');
        }
    });
}

// ─── 任务相关 ────────────────────────────────────────────────────────────────

function loadTasks() {
    apiRequest('/api/tasks').then(function (data) {
        if (data.success) {
            displayTasks(data.tasks);
        }
    });
}

function displayTasks(tasks) {
    var tbody = document.getElementById('taskBody');
    tbody.innerHTML = '';

    if (!tasks || tasks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-row">暂无任务</td></tr>';
        return;
    }

    tasks.forEach(function (task) {
        var tr = document.createElement('tr');

        // 任务名称
        var tdName = document.createElement('td');
        tdName.textContent = task.name || '';
        tr.appendChild(tdName);

        // 兑换时间
        var tdTime = document.createElement('td');
        tdTime.className = 'goods-time';
        tdTime.textContent = task.time || '';
        tr.appendChild(tdTime);

        // 请求次数
        var tdCount = document.createElement('td');
        tdCount.style.textAlign = 'center';
        tdCount.textContent = task.count || 5;
        tr.appendChild(tdCount);

        // 状态
        var tdStatus = document.createElement('td');
        tdStatus.style.textAlign = 'center';
        tdStatus.textContent = task.running ? '运行中' : '未运行';
        if (task.running) {
            tdStatus.style.color = 'var(--success)';
            tdStatus.style.fontWeight = 'bold';
        }
        tr.appendChild(tdStatus);

        // 操作
        var tdAction = document.createElement('td');
        var btnGroup = document.createElement('div');
        btnGroup.className = 'btn-group';

        if (task.running) {
            var stopBtn = document.createElement('button');
            stopBtn.className = 'btn btn-secondary btn-sm';
            stopBtn.textContent = '停止';
            stopBtn.onclick = function () {
                stopTask(task.name);
            };
            btnGroup.appendChild(stopBtn);
        } else {
            var startBtn = document.createElement('button');
            startBtn.className = 'btn btn-success btn-sm';
            startBtn.textContent = '启动';
            startBtn.onclick = function () {
                startTask(task.name);
            };
            btnGroup.appendChild(startBtn);

            var deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn btn-danger btn-sm';
            deleteBtn.textContent = '删除';
            deleteBtn.onclick = function () {
                deleteTask(task.name);
            };
            btnGroup.appendChild(deleteBtn);
        }

        tdAction.appendChild(btnGroup);
        tr.appendChild(tdAction);

        tbody.appendChild(tr);
    });
}

function showCreateTaskDialog() {
    document.getElementById('createTaskModal').style.display = 'flex';
    document.getElementById('taskName').value = '';

    // 加载心愿单
    apiRequest('/api/wishlist').then(function (data) {
        if (data.success) {
            wishlistData = data.wishlist || [];
            var select = document.getElementById('taskGoods');
            select.innerHTML = '';

            if (wishlistData.length === 0) {
                var opt = document.createElement('option');
                opt.value = '';
                opt.textContent = '心愿单为空，请先添加商品';
                select.appendChild(opt);
            } else {
                wishlistData.forEach(function (item, index) {
                    var opt = document.createElement('option');
                    opt.value = index;
                    opt.textContent = item.name + ' - ' + (item.time || '未知时间');
                    select.appendChild(opt);
                });
                onTaskGoodsChanged();
            }
        }
    });

    // 加载地址
    apiRequest('/api/addresses').then(function (data) {
        if (data.success) {
            var select = document.getElementById('taskAddress');
            select.innerHTML = '';
            (data.addresses || []).forEach(function (addr) {
                var opt = document.createElement('option');
                opt.value = addr.id || '';
                opt.textContent = addr.addr_ext || '未知地址';
                select.appendChild(opt);
            });
        }
    });

    // 默认兑换时间
    var now = new Date();
    var timeStr = now.getFullYear() + '-' +
        String(now.getMonth() + 1).padStart(2, '0') + '-' +
        String(now.getDate()).padStart(2, '0') + 'T' +
        String(now.getHours()).padStart(2, '0') + ':' +
        String(now.getMinutes()).padStart(2, '0') + ':' +
        String(now.getSeconds()).padStart(2, '0');
    document.getElementById('taskTime').value = timeStr;
}

function onTaskGoodsChanged() {
    var select = document.getElementById('taskGoods');
    var index = parseInt(select.value);
    if (isNaN(index) || !wishlistData[index]) return;

    var item = wishlistData[index];
    if (item.time) {
        // 转换时间格式
        var dt = item.time.replace(' ', 'T');
        document.getElementById('taskTime').value = dt;
    }
}

function createTask() {
    var name = document.getElementById('taskName').value.trim();
    if (!name) {
        showToast('请输入任务名称', 'error');
        return;
    }

    var goodsSelect = document.getElementById('taskGoods');
    var goodsIndex = parseInt(goodsSelect.value);
    if (isNaN(goodsIndex) || !wishlistData[goodsIndex]) {
        showToast('请选择商品', 'error');
        return;
    }

    var goods = wishlistData[goodsIndex];
    var timeValue = document.getElementById('taskTime').value;
    if (!timeValue) {
        showToast('请设置兑换时间', 'error');
        return;
    }

    // 转换时间格式
    var timeStr = timeValue.replace('T', ' ');

    var addressId = document.getElementById('taskAddress').value;
    var count = parseInt(document.getElementById('taskCount').value) || 5;

    apiRequest('/api/tasks', {
        method: 'POST',
        body: {
            name: name,
            goods_id: goods.id,
            game_biz: goods.biz || '',
            address_id: addressId,
            time: timeStr,
            count: count,
        },
    }).then(function (data) {
        if (data.success) {
            showToast('任务创建成功', 'success');
            closeModal();
            loadTasks();
        } else {
            showToast(data.message || '创建失败', 'error');
        }
    });
}

function closeModal() {
    document.getElementById('createTaskModal').style.display = 'none';
}

function startTask(taskName) {
    apiRequest('/api/tasks/' + encodeURIComponent(taskName) + '/start', {
        method: 'POST',
    }).then(function (data) {
        if (data.success) {
            showToast('任务已启动', 'success');
            loadTasks();
        } else {
            showToast(data.message || '启动失败', 'error');
        }
    });
}

function stopTask(taskName) {
    apiRequest('/api/tasks/' + encodeURIComponent(taskName) + '/stop', {
        method: 'POST',
    }).then(function (data) {
        if (data.success) {
            showToast('任务已停止', 'success');
            loadTasks();
        } else {
            showToast(data.message || '停止失败', 'error');
        }
    });
}

function deleteTask(taskName) {
    if (!confirm('确定要删除任务 "' + taskName + '" 吗？')) return;

    apiRequest('/api/tasks/' + encodeURIComponent(taskName), {
        method: 'DELETE',
    }).then(function (data) {
        if (data.success) {
            showToast('任务已删除', 'success');
            loadTasks();
        } else {
            showToast(data.message || '删除失败', 'error');
        }
    });
}

function clearTasks() {
    if (!confirm('确定要清空任务列表吗？')) return;

    apiRequest('/api/tasks/clear', { method: 'DELETE' }).then(function (data) {
        if (data.success) {
            showToast('任务列表已清空', 'success');
            loadTasks();
        } else {
            showToast(data.message || '清空失败', 'error');
        }
    });
}

// ─── 日志 ────────────────────────────────────────────────────────────────────

function viewLogs() {
    document.getElementById('logModal').style.display = 'flex';
    loadLogContent();
}

function loadLogContent() {
    apiRequest('/api/logs').then(function (data) {
        if (data.success) {
            var textarea = document.getElementById('logContent');
            textarea.value = data.content || '暂无日志';
            textarea.scrollTop = textarea.scrollHeight;
        }
    });
}

function clearLogFile() {
    if (!confirm('确定要清空日志吗？')) return;
    // 通过删除文件来清空 - 这里简单用前端清空显示
    document.getElementById('logContent').value = '';
    showToast('日志已清空', 'success');
}

function closeLogModal() {
    document.getElementById('logModal').style.display = 'none';
}

// ─── 关于 ────────────────────────────────────────────────────────────────────

function showAbout() {
    document.getElementById('aboutModal').style.display = 'flex';
}

function closeAboutModal() {
    document.getElementById('aboutModal').style.display = 'none';
}

// ─── 对话框点击外部关闭 ──────────────────────────────────────────────────────

document.querySelectorAll('.modal-overlay').forEach(function (overlay) {
    overlay.addEventListener('click', function (e) {
        if (e.target === this) {
            this.style.display = 'none';
        }
    });
});

// ─── 初始化 ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
    checkLoginStatus();
    loadGames();
    loadTasks();
});
