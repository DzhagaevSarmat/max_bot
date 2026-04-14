<?php
header('Content-Type: application/json');

$host = 'localhost';
$dbname = 'cf20821_math';
$user = 'cf20821_math';      
$pass = 'xbsas5kf9';

$VALID_TOKEN = 'mySecretToken777'; 

$received_token = $_GET['token'] ?? $_SERVER['HTTP_X_API_TOKEN'] ?? null;

if (!$received_token || $received_token !== $VALID_TOKEN) {
    http_response_code(401);
    echo json_encode([
        'error' => 'Доступ запрещён. Требуется нормальный токен.',
        'hint' => 'Передайте token в GET-параметре: ?token=ваш_токен'
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

try {
    $pdo = new PDO("mysql:host=$host;dbname=$dbname;charset=utf8", $user, $pass);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    
    $stmt = $pdo->query("SHOW TABLES");
    $tables = $stmt->fetchAll(PDO::FETCH_COLUMN);
    
    $result = [];
    
    foreach ($tables as $table) {
        $dataStmt = $pdo->query("SELECT * FROM `$table`");
        $rows = $dataStmt->fetchAll(PDO::FETCH_ASSOC);
        
        $result[$table] = [
            'count' => count($rows),
            'data' => $rows
        ];
    }
    
    echo json_encode([
        'database' => $dbname,
        'export_time' => date('Y-m-d H:i:s'),
        'total_tables' => count($tables),
        'tables' => $result
    ], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
    
} catch (Exception $e) {
    echo json_encode(['error' => $e->getMessage()]);
}
?>