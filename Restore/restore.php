<?php
header('Content-Type: application/json');

$host = 'localhost';
$dbname = 'cf20821_math';
$user = 'cf20821_math';      
$pass = 'xbsas5kf9';

$VALID_TOKEN = 'mySecretToken777';

$received_token = $_GET['token'] ?? null;

if (!$received_token || $received_token !== $VALID_TOKEN) {
    http_response_code(401);
    echo json_encode(['error' => 'Доступ запрещён']);
    exit;
}

$backupNum = $_GET['backup'] ?? null;

if (!$backupNum || !is_numeric($backupNum) || $backupNum < 1 || $backupNum > 5) {
    echo json_encode([
        'error' => 'Укажите номер бэкапа от 1 до 5',
        'hint' => 'Пример: ?token=...&backup=1 (1 - свежий, 5 - старый)'
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

$backupDir = __DIR__ . '/backups';

if (!file_exists($backupDir)) {
    echo json_encode(['error' => 'Папка с бэкапами не найдена']);
    exit;
}

$backupFiles = glob($backupDir . '/backup_*.json');
usort($backupFiles, function($a, $b) {
    return filemtime($b) - filemtime($a);
});

if (count($backupFiles) === 0) {
    echo json_encode(['error' => 'Нет доступных бэкапов']);
    exit;
}

$backupIndex = $backupNum - 1;
if (!isset($backupFiles[$backupIndex])) {
    echo json_encode([
        'error' => "Бэкап №$backupNum не найден",
        'available_backups' => count($backupFiles)
    ]);
    exit;
}

$selectedBackup = $backupFiles[$backupIndex];
$backupContent = file_get_contents($selectedBackup);
$backupData = json_decode($backupContent, true);

if (!$backupData) {
    echo json_encode(['error' => 'Ошибка чтения бэкапа: неверный JSON']);
    exit;
}

try {
    $pdo = new PDO("mysql:host=$host;dbname=$dbname;charset=utf8", $user, $pass);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    
    // Проверка, были ли изменения: 
    $hasChanges = false;
    $changesReport = [];
    
    foreach ($backupData['tables'] as $tableName => $tableData) {
        // Проверяем, существует ли таблица
        $checkTable = $pdo->query("SHOW TABLES LIKE '$tableName'");
        if ($checkTable->rowCount() == 0) {
            $hasChanges = true;
            $changesReport[] = [
                'table' => $tableName,
                'status' => 'table_missing',
                'message' => 'Таблица отсутствует в базе данных'
            ];
            continue;
        }
        
        // Считаем текущее количество записей
        $stmt = $pdo->query("SELECT COUNT(*) FROM `$tableName`");
        $currentCount = $stmt->fetchColumn();
        $backupCount = count($tableData['data']);
        
        if ($currentCount != $backupCount) {
            $hasChanges = true;
            $changesReport[] = [
                'table' => $tableName,
                'current_count' => $currentCount,
                'backup_count' => $backupCount,
                'diff' => $currentCount - $backupCount
            ];
        }
    }
    
    if (!$hasChanges) {
        echo json_encode([
            'success' => false,
            'message' => 'База данных не требует восстановления',
            'reason' => 'Текущие данные совпадают с выбранным бэкапом',
            'checked_backup' => pathinfo($selectedBackup, PATHINFO_BASENAME),
            'backup_number' => $backupNum,
            'tables_checked' => count($backupData['tables'])
        ], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
        exit;
    }
    // Конец проверки
    
    // Если есть изменения — восстанавливаем
    $pdo->exec("SET FOREIGN_KEY_CHECKS = 0");
    
    $restoredTables = [];
    $failedTables = [];
    
    foreach ($backupData['tables'] as $tableName => $tableData) {
        try {
            $pdo->exec("TRUNCATE TABLE `$tableName`");
            
            if (count($tableData['data']) > 0) {
                $columns = array_keys($tableData['data'][0]);
                $placeholders = ':' . implode(', :', $columns);
                $sql = "INSERT INTO `$tableName` (`" . implode('`, `', $columns) . "`) VALUES ($placeholders)";
                $stmt = $pdo->prepare($sql);
                
                foreach ($tableData['data'] as $row) {
                    $stmt->execute($row);
                }
            }
            
            $restoredTables[] = $tableName;
            
        } catch (PDOException $e) {
            $failedTables[] = [
                'table' => $tableName,
                'error' => $e->getMessage()
            ];
        }
    }
    
    $pdo->exec("SET FOREIGN_KEY_CHECKS = 1");
    
    $backupInfo = pathinfo($selectedBackup);
    
    echo json_encode([
        'success' => true,
        'message' => 'База данных восстановлена',
        'backup_used' => $backupInfo['basename'],
        'backup_number' => $backupNum,
        'changes_detected' => $changesReport,
        'tables_restored' => count($restoredTables),
        'tables_failed' => count($failedTables),
        'failed_details' => $failedTables
    ], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
    
} catch (Exception $e) {
    $pdo->exec("SET FOREIGN_KEY_CHECKS = 1");
    echo json_encode(['error' => $e->getMessage()]);
}
?>