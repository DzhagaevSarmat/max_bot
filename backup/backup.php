<?php

$host = 'localhost';
$dbname = 'cf20821_math';
$user = 'cf20821_math';      
$pass = 'xbsas5kf9';

$VALID_TOKEN = 'mySecretToken777';
$MAX_BACKUPS = 5; // храним последние 5 бэкапов

// Проверяем токен
$received_token = $_GET['token'] ?? null;

if (!$received_token || $received_token !== $VALID_TOKEN) {
    http_response_code(401);
    die(json_encode(['error' => 'Доступ запрещён']));
}

// Создаём папку backups, если её нет
$backupDir = __DIR__ . '/backups';
if (!file_exists($backupDir)) {
    mkdir($backupDir, 0755, true);
}

try {
    $pdo = new PDO("mysql:host=$host;dbname=$dbname;charset=utf8", $user, $pass);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    
    // Получаем все таблицы
    $stmt = $pdo->query("SHOW TABLES");
    $tables = $stmt->fetchAll(PDO::FETCH_COLUMN);
    
    $backup = [
        'database' => $dbname,
        'export_time' => date('Y-m-d H:i:s'),
        'tables' => []
    ];
    
    foreach ($tables as $table) {
        // Структура таблицы
        $schemaStmt = $pdo->query("DESCRIBE `$table`");
        $schema = $schemaStmt->fetchAll(PDO::FETCH_ASSOC);
        
        // Данные таблицы
        $dataStmt = $pdo->query("SELECT * FROM `$table`");
        $data = $dataStmt->fetchAll(PDO::FETCH_ASSOC);
        
        $backup['tables'][$table] = [
            'schema' => $schema,
            'data' => $data
        ];
    }
    
    // Имя нового бэкапа
    $filename = "backup_{$dbname}_" . date('Y-m-d_H-i-s') . ".json";
    $filepath = $backupDir . '/' . $filename;
    
    // Сохраняем файл на сервер
    file_put_contents($filepath, json_encode($backup, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    
    // Ограничиваем количество бэкапов до 5
    $backupFiles = glob($backupDir . '/backup_*.json');
    
    // Сортируем по дате создания (старые первые)
    usort($backupFiles, function($a, $b) {
        return filemtime($a) - filemtime($b);
    });
    
    // Удаляем старые бэкапы, если их больше MAX_BACKUPS
    while (count($backupFiles) > $MAX_BACKUPS) {
        $oldest = array_shift($backupFiles);
        unlink($oldest);
    }
    
    // Возвращаем ответ
    echo json_encode([
        'success' => true,
        'message' => 'Бэкап успешно создан',
        'filename' => $filename,
        'total_backups' => count(glob($backupDir . '/backup_*.json')),
        'backup_path' => "/api_project/backups/" . $filename
    ], JSON_UNESCAPED_UNICODE);
    
} catch (Exception $e) {
    echo json_encode(['error' => $e->getMessage()]);
}
?>