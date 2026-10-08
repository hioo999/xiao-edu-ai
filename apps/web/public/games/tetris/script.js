const canvas = document.getElementById('game-canvas');
const ctx = canvas.getContext('2d');
const nextCanvas = document.getElementById('next-canvas');
const nextCtx = nextCanvas.getContext('2d');

const BLOCK_SIZE = 30;
const COLS = 10;
const ROWS = 20;

const COLORS = [
    null,
    '#00FFFF', // I - Cyan
    '#0000FF', // J - Blue
    '#FFA500', // L - Orange
    '#FFFF00', // O - Yellow
    '#00FF00', // S - Green
    '#800080', // T - Purple
    '#FF0000'  // Z - Red
];

// Inner colors for 3D effect
const LIGHT_COLORS = [
    null,
    '#ccffff', '#ccccff', '#ffebcc', '#ffffcc', '#ccffcc', '#e6cce6', '#ffcccc'
];
const DARK_COLORS = [
    null,
    '#008080', '#000080', '#cc8400', '#cccc00', '#008000', '#4d004d', '#800000'
];

const SHAPES = [
    [],
    // I
    [[0,0,0,0],
     [1,1,1,1],
     [0,0,0,0],
     [0,0,0,0]],
    // J
    [[2,0,0],
     [2,2,2],
     [0,0,0]],
    // L
    [[0,0,3],
     [3,3,3],
     [0,0,0]],
    // O
    [[4,4],
     [4,4]],
    // S
    [[0,5,5],
     [5,5,0],
     [0,0,0]],
    // T
    [[0,6,0],
     [6,6,6],
     [0,0,0]],
    // Z
    [[7,7,0],
     [0,7,7],
     [0,0,0]]
];

let board = [];
let piece = null;
let nextPiece = null;
let score = 0;
let lines = 0;
let level = 1;
let dropCounter = 0;
let dropInterval = 1000;
let lastTime = 0;
let isPaused = false;
let isGameOver = false;
let animationId = null;

// DOM Elements
const scoreEl = document.getElementById('score');
const linesEl = document.getElementById('lines');
const levelEl = document.getElementById('level');
const finalScoreEl = document.getElementById('final-score');
const gameOverScreen = document.getElementById('game-over-screen');
const pauseScreen = document.getElementById('pause-screen');
const startScreen = document.getElementById('start-screen');

// Audio Context (Optional - placeholders for sound effects)
// function playSound(type) { ... }

function createMatrix(w, h) {
    const matrix = [];
    while (h--) {
        matrix.push(new Array(w).fill(0));
    }
    return matrix;
}

function createPiece() {
    const typeId = Math.floor(Math.random() * 7) + 1;
    return {
        matrix: SHAPES[typeId],
        pos: { x: Math.floor(COLS / 2) - Math.floor(SHAPES[typeId][0].length / 2), y: 0 },
        typeId: typeId
    };
}

function drawBlock(ctx, x, y, typeId, size = BLOCK_SIZE) {
    // Draw Main Color
    ctx.fillStyle = COLORS[typeId];
    ctx.fillRect(x * size, y * size, size, size);

    // Draw 3D Bevel effect
    ctx.fillStyle = LIGHT_COLORS[typeId];
    ctx.beginPath();
    ctx.moveTo(x * size, y * size);
    ctx.lineTo(x * size + size, y * size);
    ctx.lineTo(x * size + size - 4, y * size + 4);
    ctx.lineTo(x * size + 4, y * size + 4);
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(x * size, y * size);
    ctx.lineTo(x * size, y * size + size);
    ctx.lineTo(x * size + 4, y * size + size - 4);
    ctx.lineTo(x * size + 4, y * size + 4);
    ctx.fill();

    ctx.fillStyle = DARK_COLORS[typeId];
    ctx.beginPath();
    ctx.moveTo(x * size + size, y * size);
    ctx.lineTo(x * size + size, y * size + size);
    ctx.lineTo(x * size + size - 4, y * size + size - 4);
    ctx.lineTo(x * size + size - 4, y * size + 4);
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(x * size, y * size + size);
    ctx.lineTo(x * size + size, y * size + size);
    ctx.lineTo(x * size + size - 4, y * size + size - 4);
    ctx.lineTo(x * size + 4, y * size + size - 4);
    ctx.fill();

    // Inner Square
    ctx.fillStyle = COLORS[typeId];
    ctx.fillRect(x * size + 4, y * size + 4, size - 8, size - 8);
}

function drawMatrix(matrix, offset, ctxToDraw = ctx, size = BLOCK_SIZE) {
    matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value !== 0) {
                drawBlock(ctxToDraw, x + offset.x, y + offset.y, value, size);
            }
        });
    });
}

function drawGrid() {
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;

    for (let c = 0; c <= COLS; c++) {
        ctx.beginPath();
        ctx.moveTo(c * BLOCK_SIZE, 0);
        ctx.lineTo(c * BLOCK_SIZE, canvas.height);
        ctx.stroke();
    }

    for (let r = 0; r <= ROWS; r++) {
        ctx.beginPath();
        ctx.moveTo(0, r * BLOCK_SIZE);
        ctx.lineTo(canvas.width, r * BLOCK_SIZE);
        ctx.stroke();
    }
}

function drawNextPiece() {
    nextCtx.clearRect(0, 0, nextCanvas.width, nextCanvas.height);

    // Draw faint grid for next piece area
    nextCtx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    nextCtx.lineWidth = 1;
    const ns = 24; // smaller block size for next preview
    for(let i=0; i<=5; i++) {
        nextCtx.beginPath(); nextCtx.moveTo(i*ns, 0); nextCtx.lineTo(i*ns, nextCanvas.height); nextCtx.stroke();
        nextCtx.beginPath(); nextCtx.moveTo(0, i*ns); nextCtx.lineTo(nextCanvas.width, i*ns); nextCtx.stroke();
    }

    if (nextPiece) {
        // Center the piece
        const width = nextPiece.matrix[0].length;
        const height = nextPiece.matrix.length;
        const offsetX = (5 - width) / 2;
        const offsetY = (5 - height) / 2;

        drawMatrix(nextPiece.matrix, {x: offsetX, y: offsetY}, nextCtx, ns);
    }
}

function drawGhostPiece() {
    if (!piece || isGameOver) return;

    const ghost = {
        matrix: piece.matrix,
        pos: { x: piece.pos.x, y: piece.pos.y }
    };

    while (!collide(board, ghost)) {
        ghost.pos.y++;
    }
    ghost.pos.y--; // go up one step back to valid pos

    // Draw ghost outline
    ctx.fillStyle = 'rgba(255, 255, 255, 0.15)';
    ctx.strokeStyle = 'rgba(255,255,255,0.4)';
    ctx.lineWidth = 2;

    ghost.matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value !== 0) {
                const gx = (ghost.pos.x + x) * BLOCK_SIZE;
                const gy = (ghost.pos.y + y) * BLOCK_SIZE;
                ctx.fillRect(gx, gy, BLOCK_SIZE, BLOCK_SIZE);
                ctx.strokeRect(gx + 1, gy + 1, BLOCK_SIZE - 2, BLOCK_SIZE - 2);
            }
        });
    });
}

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawGrid();
    drawMatrix(board, { x: 0, y: 0 });
    drawGhostPiece();
    if (piece) {
        drawMatrix(piece.matrix, piece.pos);
    }
}

function collide(board, piece) {
    const m = piece.matrix;
    const o = piece.pos;
    for (let y = 0; y < m.length; ++y) {
        for (let x = 0; x < m[y].length; ++x) {
            if (m[y][x] !== 0 &&
               (board[y + o.y] && board[y + o.y][x + o.x]) !== 0) {
                return true;
            }
        }
    }
    return false;
}

function merge(board, piece) {
    piece.matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value !== 0) {
                board[y + piece.pos.y][x + piece.pos.x] = value;
            }
        });
    });
}

function rotate(matrix, dir) {
    // Transpose
    for (let y = 0; y < matrix.length; ++y) {
        for (let x = 0; x < y; ++x) {
            [
                matrix[x][y],
                matrix[y][x],
            ] = [
                matrix[y][x],
                matrix[x][y],
            ];
        }
    }
    // Reverse rows to complete rotation
    if (dir > 0) {
        matrix.forEach(row => row.reverse());
    } else {
        matrix.reverse();
    }
}

function pieceRotate() {
    const pos = piece.pos.x;
    let offset = 1;
    rotate(piece.matrix, 1);
    while (collide(board, piece)) {
        piece.pos.x += offset;
        offset = -(offset + (offset > 0 ? 1 : -1));
        if (offset > piece.matrix[0].length) {
            rotate(piece.matrix, -1);
            piece.pos.x = pos;
            return;
        }
    }
}

function pieceMove(dir) {
    piece.pos.x += dir;
    if (collide(board, piece)) {
        piece.pos.x -= dir;
    }
}

function pieceDrop() {
    piece.pos.y++;
    if (collide(board, piece)) {
        piece.pos.y--;
        merge(board, piece);
        resetPiece();
        arenaSweep();
        updateScore();
    }
    dropCounter = 0;
}

function pieceHardDrop() {
    while (!collide(board, piece)) {
        piece.pos.y++;
    }
    piece.pos.y--;
    merge(board, piece);
    resetPiece();
    arenaSweep();
    updateScore();
    dropCounter = 0;
}

function resetPiece() {
    if (!nextPiece) {
        nextPiece = createPiece();
    }
    piece = nextPiece;
    nextPiece = createPiece();
    drawNextPiece();

    // Check game over
    if (collide(board, piece)) {
        gameOver();
    }
}

function arenaSweep() {
    let rowCount = 0;
    outer: for (let y = board.length - 1; y >= 0; --y) {
        for (let x = 0; x < board[y].length; ++x) {
            if (board[y][x] === 0) {
                continue outer;
            }
        }
        // Found a full row
        const row = board.splice(y, 1)[0].fill(0);
        board.unshift(row);
        ++y;
        rowCount++;
    }

    if (rowCount > 0) {
        // Classic scoring system
        const lineScores = [0, 40, 100, 300, 1200];
        score += lineScores[rowCount] * level;
        lines += rowCount;
        level = Math.floor(lines / 10) + 1;
        // Speed up
        dropInterval = Math.max(100, 1000 - (level - 1) * 100);
    }
}

function updateScore() {
    scoreEl.innerText = score;
    linesEl.innerText = lines;
    levelEl.innerText = level;
}

function gameOver() {
    isGameOver = true;
    cancelAnimationFrame(animationId);
    finalScoreEl.innerText = score;
    gameOverScreen.style.display = 'flex';
}

function resetGame() {
    board = createMatrix(COLS, ROWS);
    score = 0;
    lines = 0;
    level = 1;
    dropInterval = 1000;
    isGameOver = false;
    isPaused = false;
    nextPiece = null;
    gameOverScreen.style.display = 'none';
    pauseScreen.style.display = 'none';
    startScreen.style.display = 'none';

    updateScore();
    resetPiece();
    lastTime = performance.now();
    update();
}

function togglePause() {
    if (isGameOver || startScreen.style.display !== 'none') return;

    isPaused = !isPaused;
    if (isPaused) {
        cancelAnimationFrame(animationId);
        pauseScreen.style.display = 'flex';
        document.getElementById('pause-btn').innerText = 'RESUME';
    } else {
        pauseScreen.style.display = 'none';
        document.getElementById('pause-btn').innerText = 'PAUSE';
        lastTime = performance.now();
        update();
    }
}

function update(time = 0) {
    if (isPaused || isGameOver) return;

    const deltaTime = time - lastTime;
    lastTime = time;

    dropCounter += deltaTime;
    if (dropCounter > dropInterval) {
        pieceDrop();
    }

    draw();
    animationId = requestAnimationFrame(update);
}

// Controls
document.addEventListener('keydown', event => {
    if (isPaused && event.key !== 'p' && event.key !== 'P') return;
    if (isGameOver) return;
    if (startScreen.style.display !== 'none') return;

    switch (event.keyCode) {
        case 37: // Left
            pieceMove(-1);
            break;
        case 39: // Right
            pieceMove(1);
            break;
        case 40: // Down
            pieceDrop();
            break;
        case 38: // Up (Rotate)
            pieceRotate();
            break;
        case 32: // Space (Hard Drop)
            pieceHardDrop();
            break;
        case 80: // P (Pause)
            togglePause();
            break;
    }
    draw(); // Immediate visual update
});

// Button Events
document.getElementById('start-btn').addEventListener('click', resetGame);
document.getElementById('restart-btn').addEventListener('click', resetGame);
document.getElementById('restart-btn-overlay').addEventListener('click', resetGame);
document.getElementById('pause-btn').addEventListener('click', togglePause);

// Initial state
board = createMatrix(COLS, ROWS);
drawGrid();
drawNextPiece();
