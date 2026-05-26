<?php
header('Content-Type: application/json');

$VALID_TOKEN = 'mySecretToken777';

// Проверяем токен
$token = $_GET['token'] ?? $_POST['token'] ?? null;
if (!$token || $token !== $VALID_TOKEN) {
    http_response_code(403);
    echo json_encode(['error' => 'Доступ запрещён']);
    exit;
}

// Проверяем, что файл был отправлен
if (!isset($_FILES['json_file'])) {
    http_response_code(400);
    echo json_encode(['error' => 'Файл не найден']);
    exit;
}

$uploadDir = __DIR__ . '/post_json/';
if (!file_exists($uploadDir)) {
    mkdir($uploadDir, 0755, true);
}

$filename = 'received_' . date('Y-m-d_H-i-s') . '.json';
$filepath = $uploadDir . $filename;

if (move_uploaded_file($_FILES['json_file']['tmp_name'], $filepath)) {
    echo json_encode([
        'success' => true,
        'message' => 'Файл сохранён',
        'filename' => $filename
    ]);
} else {
    http_response_code(500);
    echo json_encode(['error' => 'Ошибка сохранения файла']);
}