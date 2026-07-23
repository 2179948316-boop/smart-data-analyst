<template>
  <div class="datasource-page">
    <div class="page-header">
      <h2>数据源管理</h2>
      <div class="header-actions">
        <el-button @click="loadTables" :loading="tablesLoading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" @click="showUploadDialog = true">
          <el-icon><Upload /></el-icon>
          上传文件
        </el-button>
        <el-button @click="showAddDialog">
          <el-icon><Plus /></el-icon>
          添加 MySQL 数据源
        </el-button>
      </div>
    </div>

    <!-- File Upload Area (always visible) -->
    <el-card shadow="hover" class="upload-card">
      <template #header>
        <div class="card-header">
          <span>导入数据文件</span>
          <el-tag type="info" size="small">支持 .xlsx / .xls / .csv / .tsv</el-tag>
        </div>
      </template>

      <el-upload
        drag
        :auto-upload="false"
        :on-change="handleFileChange"
        :file-list="fileList"
        :limit="1"
        accept=".xlsx,.xls,.csv,.tsv"
        class="upload-area"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">
          将 Excel 或 CSV 文件拖到此处，或 <em>点击选择文件</em>
        </div>
        <template #tip>
          <div class="upload-tip">
            文件大小不超过 50MB，最多 50 万行。导入后可直接用中文提问查询。
          </div>
        </template>
      </el-upload>

      <!-- Upload options -->
      <div v-if="selectedFile" class="upload-options">
        <el-form inline>
          <el-form-item label="表名（可选）">
            <el-input
              v-model="customTableName"
              placeholder="留空则使用文件名"
              clearable
              style="width: 220px"
            />
          </el-form-item>
          <el-form-item label="同名表">
            <el-select v-model="ifExists" style="width: 130px">
              <el-option label="自动重命名" value="rename" />
              <el-option label="覆盖原表" value="replace" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="doUpload" :loading="uploading">
              导入到数据库
            </el-button>
            <el-button @click="cancelUpload">取消</el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- Upload result -->
      <el-result
        v-if="uploadResult"
        :icon="uploadResult.success ? 'success' : 'error'"
        :title="uploadResult.title"
        :sub-title="uploadResult.subTitle"
      >
        <template #extra>
          <div v-if="uploadResult.table" class="import-preview">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="表名">{{ uploadResult.table.table_name }}</el-descriptions-item>
              <el-descriptions-item label="行数">{{ uploadResult.table.row_count.toLocaleString() }}</el-descriptions-item>
              <el-descriptions-item label="列数">{{ uploadResult.table.column_count }}</el-descriptions-item>
            </el-descriptions>
            <el-table :data="uploadResult.table.columns" size="small" style="margin-top: 12px" max-height="200">
              <el-table-column prop="name" label="列名" />
              <el-table-column prop="type" label="MySQL 类型" />
            </el-table>
          </div>
          <el-button @click="uploadResult = null" style="margin-top: 12px">关闭</el-button>
        </template>
      </el-result>
    </el-card>

    <!-- Tables in Database (dynamic) -->
    <el-card shadow="hover" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>数据库表列表</span>
          <el-tag type="info" size="small">{{ allTables.length }} 张表</el-tag>
        </div>
      </template>
      <el-table :data="allTables" stripe v-loading="tablesLoading" empty-text="暂无数据表">
        <el-table-column prop="name" label="表名" width="200">
          <template #default="{ row }">
            <span class="table-name-cell">{{ row.name }}</span>
            <el-tag v-if="isProtected(row.name)" type="warning" size="small" style="margin-left: 6px">示例</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="row_count" label="行数" width="120">
          <template #default="{ row }">
            {{ row.row_count.toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column prop="comment" label="注释" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-popconfirm
              v-if="!isProtected(row.name)"
              title="确定删除此表？删除后不可恢复。"
              @confirm="handleDeleteTable(row.name)"
            >
              <template #reference>
                <el-button type="danger" size="small" text>删除</el-button>
              </template>
            </el-popconfirm>
            <el-tooltip v-else content="示例表不允许删除" placement="top">
              <el-button type="info" size="small" text disabled>删除</el-button>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Other MySQL Data Sources -->
    <h3 style="margin: 24px 0 12px">其他 MySQL 数据源</h3>
    <el-table :data="dataSources" stripe v-loading="dsLoading" empty-text="暂无其他数据源">
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="host" label="主机" />
      <el-table-column prop="port" label="端口" width="80" />
      <el-table-column prop="database_name" label="数据库" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '活跃' : '离线' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="table_count" label="表数量" width="80" />
    </el-table>

    <!-- Upload Dialog (mobile-friendly alternative) -->
    <el-dialog v-model="showUploadDialog" title="上传数据文件" width="460px">
      <el-upload
        drag
        :auto-upload="false"
        :on-change="handleFileChange"
        :file-list="fileList"
        :limit="1"
        accept=".xlsx,.xls,.csv,.tsv"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div>拖拽或点击选择文件</div>
      </el-upload>
      <template #footer>
        <el-button @click="showUploadDialog = false">关闭</el-button>
        <el-button
          type="primary"
          @click="showUploadDialog = false; doUpload()"
          :loading="uploading"
          :disabled="!selectedFile"
        >
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <!-- Add MySQL Dialog -->
    <el-dialog v-model="addDialogVisible" title="添加 MySQL 数据源" width="500px">
      <el-form :model="newDs" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="newDs.name" placeholder="例如：生产库" />
        </el-form-item>
        <el-form-item label="主机">
          <el-input v-model="newDs.host" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="newDs.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="newDs.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="newDs.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="数据库名">
          <el-input v-model="newDs.database_name" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAdd" :loading="adding">测试连接并添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listDataSources, createDataSource, uploadFile, listTables, deleteTable } from '../api'

const PROTECTED_TABLES = new Set(['categories', 'products', 'customers', 'orders', 'order_items', 'reviews'])
const isProtected = (name) => PROTECTED_TABLES.has(name)

// Tables
const allTables = ref([])
const tablesLoading = ref(false)

// Upload
const fileList = ref([])
const selectedFile = ref(null)
const customTableName = ref('')
const ifExists = ref('rename')
const uploading = ref(false)
const uploadResult = ref(null)
const showUploadDialog = ref(false)

// MySQL data sources
const dataSources = ref([])
const dsLoading = ref(false)
const addDialogVisible = ref(false)
const adding = ref(false)
const newDs = reactive({
  name: '',
  host: 'localhost',
  port: 3306,
  username: 'root',
  password: '',
  database_name: '',
})

// Load tables from business DB
const loadTables = async () => {
  tablesLoading.value = true
  try {
    const res = await listTables()
    if (res.data.success) {
      allTables.value = res.data.tables
    }
  } catch (e) {
    console.error('Failed to load tables:', e)
  } finally {
    tablesLoading.value = false
  }
}

// Handle file selection
const handleFileChange = (file) => {
  selectedFile.value = file.raw
  fileList.value = [file]
  uploadResult.value = null
}

const cancelUpload = () => {
  selectedFile.value = null
  fileList.value = []
  customTableName.value = ''
  uploadResult.value = null
}

// Upload file
const doUpload = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  uploading.value = true
  uploadResult.value = null

  try {
    const res = await uploadFile(selectedFile.value, customTableName.value, ifExists.value)
    const data = res.data

    if (data.success) {
      uploadResult.value = {
        success: true,
        title: '导入成功',
        subTitle: data.message,
        table: data.table,
      }
      ElMessage.success(data.message)
      // Reset file selection
      selectedFile.value = null
      fileList.value = []
      customTableName.value = ''
      // Refresh table list
      loadTables()
    } else {
      uploadResult.value = {
        success: false,
        title: '导入失败',
        subTitle: data.error,
      }
      ElMessage.error(data.error)
    }
  } catch (e) {
    const msg = e.response?.data?.detail || e.message
    uploadResult.value = {
      success: false,
      title: '上传出错',
      subTitle: msg,
    }
    ElMessage.error('上传失败: ' + msg)
  } finally {
    uploading.value = false
  }
}

// Delete table
const handleDeleteTable = async (tableName) => {
  try {
    const res = await deleteTable(tableName)
    if (res.data.success) {
      ElMessage.success(res.data.message)
      loadTables()
    } else {
      ElMessage.error(res.data.error)
    }
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// MySQL data sources
const showAddDialog = () => {
  addDialogVisible.value = true
}

const handleAdd = async () => {
  adding.value = true
  try {
    const res = await createDataSource(newDs)
    if (res.data.status === 'connected') {
      ElMessage.success(`连接成功，发现 ${res.data.table_count} 张表`)
      addDialogVisible.value = false
      loadDataSources()
    } else {
      ElMessage.error(`连接失败: ${res.data.error}`)
    }
  } catch (e) {
    ElMessage.error('添加失败')
  } finally {
    adding.value = false
  }
}

const loadDataSources = async () => {
  dsLoading.value = true
  try {
    const res = await listDataSources()
    dataSources.value = res.data
  } catch (e) {
    console.error('Failed to load data sources:', e)
  } finally {
    dsLoading.value = false
  }
}

onMounted(() => {
  loadTables()
  loadDataSources()
})
</script>

<style scoped>
.datasource-page {
  padding: 24px;
  height: 100vh;
  overflow-y: auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  color: #333;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-card {
  margin-bottom: 0;
}

.upload-area {
  width: 100%;
}

.upload-icon {
  font-size: 48px;
  color: #c0c4cc;
  margin-bottom: 8px;
}

.upload-text {
  font-size: 14px;
  color: #606266;
}

.upload-text em {
  color: #409eff;
  font-style: normal;
}

.upload-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

.upload-options {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.import-preview {
  text-align: left;
  max-width: 500px;
}

.table-name-cell {
  font-family: 'Consolas', 'Monaco', monospace;
  font-weight: 600;
}

.table-tag {
  margin: 2px 4px 2px 0;
}
</style>
