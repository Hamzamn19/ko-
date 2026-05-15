# CLAUDE.md
> **Read this file completely before any task.**  
> **Never assume — always check the relevant file first.**

---

## 0. QUICK REFERENCE
- **Stack**: NestJS + Prisma + PostgreSQL + Next.js 16 + Python/YOLO
- ⚠️ **Backend changes need**: `build` → `docker cp` → `restart` (NEVER assume live reload)
- ⚠️ **Secrets**: ALWAYS use `readSecret()`, never hardcode
- ⚠️ **Student data**: encrypted via Prisma middleware, never handle manually
- **API calls**: always via `MudekApi` in `lib/api.ts`, never raw `fetch()`
- **MÜDEK threshold**: 60% hardcoded in `getZReportData()` and `generateAssessmentReport()` — never duplicate
- **Single AppModule pattern** — do NOT create feature modules

---

## 1. PROJECT OVERVIEW

**Accredita** is a MÜDEK/ABET-compliant course outcome assessment platform for Beykoz University. It processes OMR (Optical Mark Recognition) exam scans to compute CLO (Course Learning Outcome) and PLO (Program Learning Outcome) achievement scores. The system automates student assessment workflows, generates compliance reports, and provides analytics dashboards for instructors and administrators.

**Problem it solves**: Manual calculation of MÜDEK/ABET assessment metrics is time-consuming, error-prone, and lacks real-time analytics.

**Target users**: University instructors, program coordinators, administrators, and accreditation officers.

---

## 2. TECH STACK

### Backend (NestJS)
- **NestJS 10** — robust Node.js framework for enterprise APIs
- **Prisma 5.16** — type-safe ORM with PostgreSQL
- **PostgreSQL 17** — relational database for structured course/exam data
- **BullMQ 4.15** — Redis-based job queue for async OMR processing
- **Redis 7.4** — cache + queue backend
- **Passport JWT** — JWT authentication with LDAP integration
- **OpenLDAP** — centralized user authentication
- **Swagger** — auto-generated API documentation

### Reader Engine (Python)
- **FastAPI** — Python async web framework for ML inference
- **YOLOv8** — object detection model for OMR bubble recognition
- **TensorFlow 2.16 (CUDA)** — CNN-based MNIST handwriting score recognition
- **OpenCV 4.10** — image preprocessing and contour detection
- **NumPy 1.x** — numerical processing

### Frontend (Next.js)
- **Next.js 16** (App Router) — React framework with SSR/SSG
- **React 19.2** — UI library
- **Tailwind CSS v4** — utility-first CSS framework
- **shadcn/ui** — accessible, composable UI components
- **Recharts 3.5** — charting library for analytics
- **jsPDF + jspdf-autotable** — PDF report generation
- **react-hook-form + Zod** — form validation
- **Sonner** — toast notifications
- **next-themes** — dark/light mode support

### Infrastructure
- **Docker Compose** — multi-container orchestration
- **nginx** — reverse proxy and SSL termination
- **CrowdSec** — intrusion detection system

---

## 3. PROJECT STRUCTURE

```
/var/www/Accredita-Full/
├── backend/
│   ├── backend/                 # NestJS API (main backend)
│   │   ├── src/
│   │   │   ├── app.module.ts    # Root module (no feature modules)
│   │   │   ├── app.service.ts   # Core business logic
│   │   │   ├── app.controller.ts # Course/exam endpoints
│   │   │   ├── auth/            # JWT + LDAP auth
│   │   │   ├── dto/             # Data Transfer Objects
│   │   │   ├── queue/           # BullMQ scan job processor
│   │   │   ├── prisma.service.ts # Prisma client + encryption middleware
│   │   │   ├── secrets.util.ts  # Docker secrets reader
│   │   │   └── field-encryption.util.ts # AES-256-GCM encryption
│   │   ├── prisma/
│   │   │   ├── schema.prisma    # Database schema
│   │   │   ├── migrations/      # SQL migration history
│   │   │   └── seed.ts          # Seed data script
│   │   └── dist/                # Compiled JS (NOT volume-mounted)
│   └── reader-engine/           # Python OMR scanner (volume-mounted)
│       ├── server.py            # FastAPI endpoints
│       └── scan_paper.py        # YOLO inference pipeline
├── frontend/
│   ├── app/                     # Next.js App Router
│   │   ├── (dashboard)/         # Main app routes
│   │   │   ├── courses/         # Course & CLO management
│   │   │   ├── scanner/         # OMR upload UI
│   │   │   ├── verification/    # Manual result correction
│   │   │   ├── z-report/        # CLO/PLO reports
│   │   │   ├── programs/        # PLO management
│   │   │   ├── admin/           # User admin (role: admin|dev)
│   │   │   └── dev/             # Raw DB browser (role: dev)
│   │   └── agent/               # AI agent chat (outside dashboard)
│   ├── components/
│   │   ├── ui/                  # shadcn/ui components
│   │   └── [custom].tsx         # Custom components (sidebar, charts, etc.)
│   ├── lib/
│   │   ├── api.ts               # MudekApi client (all backend calls)
│   │   └── utils.ts             # Helpers (cn, etc.)
│   └── middleware.ts            # Route guards (dev/admin role checks)
├── nginx/
│   └── default.conf             # Reverse proxy config (frontend :3000, backend /api)
├── secrets/                     # Docker secrets (*.txt files)
├── docker-compose.yml           # Multi-service orchestration
└── scripts/                     # DB backup, deployment scripts
```

**Key files**:
- `backend/backend/src/app.service.ts` — ALL business logic (scanning, analytics, Z-reports)
- `backend/backend/prisma/schema.prisma` — Database schema source of truth
- `frontend/lib/api.ts` — Single API client used by all frontend pages
- `docker-compose.yml` — Service definitions and networking
- `secrets/*.txt` — All sensitive values (JWT secret, DB password, etc.)

---

## 4. ARCHITECTURE & PATTERNS

### System Flow
```
User (Browser)
  ↓ HTTP/HTTPS
nginx (:80/:443)
  ↓ Proxy /api → backend:3000
  ↓ Proxy /    → frontend:3000
  ↓
Frontend (Next.js SSR) ← MudekApi client → Backend (NestJS)
                                              ↓
                                         Prisma ORM
                                              ↓
                                         PostgreSQL
                                              ↓
                                      BullMQ (Redis queue)
                                              ↓
                                    Reader Engine (FastAPI)
                                              ↓
                                      YOLOv8 + OpenCV
```

### Authentication Flow
1. User submits credentials → `/auth/login`
2. NestJS validates via LDAP (`passport-ldapauth`)
3. On success, generate JWT (8h expiry) with payload: `{ sub: BlindID, name, email, role }`
4. Set two cookies:
   - `auth_token` (httpOnly) — JWT token
   - `user_info` (readable) — `{role, name, email}` for UI rendering
5. All routes protected by global `JwtAuthGuard` unless marked `@Public()`
6. JWT extracted from `Authorization: Bearer <token>` OR `auth_token` cookie

### OMR Scan Processing Flow
1. User uploads PDF/images → `POST /api/upload-exam-paper`
2. Files saved to `/app/uploads/{uuid}` → BullMQ job enqueued
3. Background worker calls `appService.processExamPaper()`
4. Backend HTTP request → `http://reader:5000/scan_single_paper`
5. Python YOLOv8 detects bubbles, and TensorFlow reads handwritten scores → returns JSON with answers
6. NestJS parses results → creates `StudentResult` + `QuestionResult` records
7. Encrypted `studentId` and `imagePath` stored in DB
8. SSE stream (`/api/scan-events`) sends real-time progress to frontend

### CLO/PLO Calculation (Contribution-Weighted Average)
```
CLO% = Σ(examCLO% × contribution) / Σ(contributions)
PLO% = Σ(CLO% × clo-plo-weight) / Σ(clo-plo-weights)
```
Falls back to equal weight if `ExamMetadata.extra.contribution` is missing.  
**MÜDEK threshold**: 60% (hardcoded in `getZReportData()` and `generateAssessmentReport()`).

### Design Patterns
- **Monolithic modules** — Single `AppModule` (no feature modules beyond `AuthModule`)
- **Service layer** — `AppService` handles ALL business logic
- **DTO validation** — `class-validator` decorators on all DTOs
- **Middleware encryption** — Prisma middleware auto-encrypts sensitive fields
- **Queue pattern** — BullMQ for async heavy tasks
- **API client abstraction** — Frontend uses `MudekApi` for all backend calls

---

## 4.1 APP.SERVICE.TS — KEY METHODS

This is the complete reference for all major methods in `app.service.ts`. Every public method is listed by category.

### OMR Scan Pipeline
- **processExamPaper**(file) → processes uploaded exam file, enqueues BullMQ job → `{ ...OmrScanResponse, resultId }`
- **processExamFile**(filePath, originalName) → calls Python reader engine, saves to DB → `{ ...OmrScanResponse, resultId }`
- **generateFormProxy**(queryParams) → proxies exam cover sheet generation to Python service → `ArrayBuffer` (PDF)
- **saveResultToDB**(data, imagePath) → creates `StudentResult`, `Question`, `QuestionResult` records → `StudentResult`
- **evaluateScoresWithAnswerKey**(exam, questionMap, payload) → evaluates MCQ answers against answer key → `scores[]`

### Course & CLO/PLO Management
- **getCourseMatrix**(courseCode, filters?) → fetches CLO-PLO matrix for course with term filtering → `{ courseName, programName, term, plos, matrix }`
- **getAllCourses**(user?, filters?) → lists courses accessible to user (scoped by role/assignments) → `Course[]`
- **createCourse**(code, name, programId?) → creates new course, auto-assigns to program → `Course`
- **getCLOsByCourse**(courseCode, filters?) → lists CLOs for course with term filtering → `CLO[]`
- **upsertCourseClos**(courseCode, payload) → bulk upsert CLOs for a course, handles CLO-PLO linking → transaction result
- **getAllPrograms**(user?) → lists programs accessible to user → `Program[]`
- **getAllPLOs**(options?) → lists PLOs with optional program/term filtering → `PLO[]`
- **upsertProgramPlos**(payload) → bulk upsert PLOs for a program → transaction result
- **updateMatrix**(cloId, ploId, value) → updates CLO-PLO contribution weight (1-5 scale) → `CloPloMatrix`

### Exam & Results
- **getExamHistory**(courseCode, user?) → lists all exams for a course → `Exam[]`
- **getExamResults**(examId) → fetches all student results for an exam → `Exam` with results
- **getExamResultsByReference**(params) → resolves exam by courseCode/type/date/ref → `Exam` with results
- **getStudentResult**(studentId, options?) → fetches individual student result with filters → `StudentResult`
- **createExamWithQuestions**(body) → creates exam with predefined questions → `Exam`
- **fillStudentScores**(examId, body) → bulk insert student scores for manually created exam → transaction result
- **upsertExamMetadata**(payload) → stores exam metadata (question count, gridYOffset, contribution, cloMap) → `ExamMetadata`
- **getExamMetadata**(examRef) → fetches exam metadata by examRef or falls back to exam lookup → metadata object

### Manual Corrections
- **overrideScanResult**(resultId, payload) → manual override of entire student result → updated `StudentResult`
- **overrideScanResultByMetadata**(params, payload) → overrides result by exam reference + studentId → updated `StudentResult`
- **overrideSingleAnswer**(resultId, questionRef, payload) → corrects single answer in a result → updated `StudentResult`

### Analytics & Reports
- **getExamAnalyticsByReference**(params) → fetches analytics for a specific exam (distribution, radar, students) → `{ distribution, radar, students }`
- **getExamAnalyticsById**(examId) → analytics for exam by ID → `ExamAnalyticsResponse`
- **getLatestExamDistribution**() → score distribution of most recent scan → `{ courseCode, distribution, studentCount }`
- **getCourseOverallAnalytics**(params) → aggregates all exams for a course → `{ distribution, radar, students }`
- **getZReportData**(courseCode, options?) → generates Z-report data with CLO/PLO achievement (contribution-weighted) → `{ course, cloResults, ploResults, studentList, statistics }`
- **generateAssessmentReport**(examId) → generates MÜDEK assessment report data → report object
- **getPloScoresForProgram**(params) → calculates PLO achievement for entire program → `{ programName, ploScores }`

### Helper Methods (private)
- **resolveScopedAssignments**(user?) → resolves user's accessible courses/programs based on role/assignments → `{ courseCodes, programIds, visibleProgramIds }`
- **assertCourseAccess**(courseCode, user?) → throws 403 if user cannot access course → void
- **prepareMultipleChoiceExam**(queryParams) → creates exam record for MCQ form generation → `examId`
- **ensureCourse**(code, name?) → finds or creates course by code → `Course`
- **buildExamTitle**(code, examType?, examDate?) → generates exam title string → `string`
- **resolveTerm**(options?) → resolves academic term (creates if missing, falls back to latest) → `AcademicTerm | null`
- **fetchClosForCourse**(courseId, options?) → fetches CLOs for course with term resolution → `{ clos, term }`
- **fetchPlosForProgram**(programId, options?) → fetches PLOs for program with term resolution → `{ plos, term }`
- **syncCloPloLinks**(cloId, plos?, allowedPloIds?) → syncs CLO-PLO matrix relationships → void
- **resolveExamForAnalytics**(params, options?) → resolves exam by multiple criteria (courseCode, ref, type, date, term) → `Exam | null`
- **buildTermDateRange**(year, season) → calculates date range for academic term → `{ start, end }`
- **buildScoreDistribution**(scores) → builds histogram buckets (20-point intervals) → `{ range, count }[]`
- **buildCloRadar**(exam) → calculates CLO performance radar chart data → `{ clo, score }[]`
- **mapLetterGrade**(score) → converts numeric score to letter grade → `string`
- **getAcademicTerms**() → lists all academic terms → `AcademicTerm[]`
- **isV2ScopedRoleAccessEnabled**() → checks if scoped access control is enabled → `boolean`
- **setV2ScopedRoleAccessEnabled**(enabled) → toggles scoped access control → `boolean`

---

## 5. CODING CONVENTIONS

### Backend (NestJS)
```typescript
// DTOs: class-validator decorators
export class CreateCourseDto {
  @IsString()
  @IsNotEmpty()
  code: string;

  @IsInt()
  programId: number;
}

// Controllers: route prefix + guards
@Controller('api/courses')
@UseGuards(JwtAuthGuard, RolesGuard)
export class AppController {
  @Get(':code/analytics')
  @Roles('instructor', 'admin', 'dev')
  async getAnalytics(@Param('code') code: string) { ... }
}

// Services: inject Prisma, no direct DB access in controllers
constructor(private prisma: PrismaService) {}

// Error responses: NestJS exceptions
throw new NotFoundException(`Course ${code} not found`);
throw new BadRequestException('Invalid exam format');
throw new UnauthorizedException('Insufficient permissions');

// API responses: plain objects (auto-serialized)
return { success: true, data: course };
return { cloAchievement: 72.5, ploAchievement: 68.3 };
```

### Frontend (Next.js)
```typescript
// API calls: always via MudekApi
import { MudekApi } from '@/lib/api';
const courses = await MudekApi.getCourses();
const analytics = await MudekApi.getCourseAnalytics('CME6403', 'latest');

// Components: kebab-case filenames, PascalCase exports
// sidebar.tsx → export function Sidebar()

// Utilities: camelCase
export function calculateAverage(scores: number[]) { ... }

// Styling: Tailwind classes + cn() helper
<div className={cn("bg-card p-4", isDark && "text-white")} />

// Forms: react-hook-form + Zod
const schema = z.object({ code: z.string().min(1) });
const form = useForm({ resolver: zodResolver(schema) });

// Toasts: Sonner
import { toast } from 'sonner';
toast.success('Course created');
toast.error('Failed to upload');
```

### Naming
- **Variables**: `camelCase` — `studentResults`, `cloAchievement`
- **Functions**: `camelCase` — `getCourseAnalytics()`, `processExamPaper()`
- **Classes/Interfaces**: `PascalCase` — `CreateCourseDto`, `StudentResult`
- **Files**: `kebab-case.ts` — `app.service.ts`, `clo-chart.tsx`
- **Database fields**: `camelCase` — Prisma auto-converts to snake_case SQL

### Error Handling
- Backend: Throw NestJS exceptions (`NotFoundException`, `BadRequestException`)
- Frontend: Try-catch with toast notifications
- Never swallow errors silently — always log or notify user

---

## 6. CRITICAL RULES (⚠️ NEVER VIOLATE)

### 1. Backend Source NOT Volume-Mounted
**⚠️ CRITICAL**: Backend `dist/` folder is NOT live-mounted. Every code change requires:
```bash
cd /var/www/Accredita-Full/backend/backend
npm run build
docker cp dist/<changed-file>.js backend:/app/dist/<changed-file>.js
docker restart backend
```
Forgetting this will make changes appear to "not work".

### 2. Never Hardcode Secrets
ALWAYS use `readSecret()` from `secrets.util.ts`:
```typescript
const jwtSecret = readSecret('JWT_SECRET'); // ✅
const jwtSecret = 'my-secret-key';         // ❌ NEVER
```
Required secrets in `./secrets/`: `jwt_secret.txt`, `postgres_password.txt`, `redis_password.txt`, `blind_id_secret.txt`, `ldap_bind_credentials.txt`, `swagger_password.txt`, `field_encryption_key.txt`.

### 3. DATABASE_URL Password Substitution
Never use `process.env.DATABASE_URL` directly. Use:
```typescript
import { getDatabaseUrl } from './secrets.util';
const url = getDatabaseUrl(); // Substitutes real password
```

### 4. Field Encryption
`StudentResult.studentId` and `StudentResult.imagePath` are auto-encrypted by Prisma middleware. Encrypted values are prefixed `enc:v1:`. **Never**:
- Store plaintext student IDs in `StudentResult` table
- Decrypt manually (Prisma middleware handles this)
- Change encryption key (`field_encryption_key.txt`) without re-encrypting DB

### 5. Blind IDs for Privacy
Use `BlindID` (HMAC-SHA256 of LDAP username) as `createdById` in all user-linked records. Never store real LDAP usernames in the database.

### 6. JWT Cookies Only
JWT stored as `httpOnly` cookie. Frontend CANNOT read it via JavaScript. `user_info` cookie is readable for UI rendering only.

### 7. Rate Limiting
Backend has global `ThrottlerGuard` (100 req/min per IP). Aggressive scraping will trigger 429 errors.

### 8. Prisma Migrations
**NEVER** edit `prisma/migrations/` manually. Always:
```bash
npx prisma migrate dev --name <description>
npx prisma generate
npm run build
```

### 9. File Uploads
- Max 50 MB (enforced by multer)
- MIME type + extension whitelist validation
- Saved to `/app/uploads/{uuid}` with randomized filenames
- Processed outputs served from `/api/static/processed/`

### 10. Role Guards
Dev routes (`/dev`, `/api/dev/*`) must have:
```typescript
@Roles('dev')
@UseGuards(RolesGuard)
```
Admin routes need `@Roles('admin', 'dev')`. Never expose dev tools to regular users.

---

## 6.1 ENVIRONMENT VARIABLES

### Backend (NestJS) — `/backend/backend/.env` & `docker-compose.yml`
```bash
# Runtime Configuration
NODE_ENV=production                    # Environment mode
PORT=3000                              # Backend server port
JWT_EXPIRES_IN=8h                      # JWT token expiration

# Service URLs (internal Docker network)
PYTHON_SERVICE_URL=http://reader:5000  # Reader engine URL
PYTHON_TIMEOUT_MS=60000                # Reader timeout in milliseconds

# Database & Cache (placeholder passwords substituted at runtime)
DATABASE_URL=postgresql://accredita_user:placeholder@db:5432/accredita_db
REDIS_URL=redis://:placeholder@redis:6379

# LDAP Configuration
LDAP_URL=ldap://openldap:389
LDAP_BIND_DN=cn=admin,dc=beykoz,dc=edu,dc=tr
LDAP_SEARCH_BASE=dc=beykoz,dc=edu,dc=tr
LDAP_SEARCH_FILTER=(|(uid={{username}})(sAMAccountName={{username}})(cn={{username}}))

# Docker Secrets (file paths read at runtime via secrets.util.ts)
JWT_SECRET_FILE=/run/secrets/jwt_secret
BLIND_ID_SECRET_FILE=/run/secrets/blind_id_secret
POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
REDIS_PASSWORD_FILE=/run/secrets/redis_password
LDAP_BIND_CREDENTIALS_FILE=/run/secrets/ldap_bind_credentials
SWAGGER_PASSWORD_FILE=/run/secrets/swagger_password
FIELD_ENCRYPTION_KEY_FILE=/run/secrets/field_encryption_key

# Swagger Configuration
SWAGGER_ENABLED=false                  # Enable Swagger docs (dev only)
SWAGGER_USER=admin                     # Swagger basic auth username

# BullMQ Queue
SCAN_QUEUE_NAME=scan-queue             # Redis queue name for scan jobs
```

### Frontend (Next.js) — `/frontend/.env.local`
```bash
# Public Variables (exposed to browser)
NEXT_PUBLIC_API_URL=                   # Empty = same-origin via nginx proxy
NEXT_PUBLIC_AUTH_URL=                  # Auth endpoints base URL (empty = same-origin)
NEXT_PUBLIC_BASE_PATH=                 # Base path for Next.js (used in V2 deployment)

# Server-Side Only
BACKEND_INTERNAL_URL=http://backend:3000  # Internal Docker network URL for SSR
JWT_SECRET_FILE=/run/secrets/jwt_secret   # JWT secret for server-side validation
NODE_ENV=production                       # Environment mode
```

### Reader Engine (Python) — `/backend/reader-engine` via `docker-compose.yml`
```bash
PYTHONUNBUFFERED=1                     # Disable Python output buffering
PROCESSED_DIR=/app/reader-processed    # Output directory for processed scans
YOLO_DEVICE=cuda                       # YOLO inference device (cuda/cpu)
BACKEND_API_URL=http://backend:3000/api  # Backend URL for callbacks
```

### V2 Services (Staging/Development)
Same variables as production but with `-v2` suffixes:
- `SCAN_QUEUE_NAME=scan-queue-v2`
- `PYTHON_SERVICE_URL=http://reader-v2:5000`
- `DATABASE_URL=...accredita_db_v2`

---

## 7. DATABASE SCHEMA

### Core Tables & Relationships
```
Program (1) ─→ (N) Course (1) ─→ (N) Exam (1) ─→ (N) StudentResult (1) ─→ (N) QuestionResult
   ↓                   ↓                               ↓
  PLO                 CLO ←──── QuestionClo ─────────→ Question
   ↑                   ↑
   └──── CloPloMatrix ─┘ (N:M mapping with contribution weight 1-5)
```

### Critical Fields
- `Course.createdById` — BlindID (HMAC-SHA256 of LDAP username)
- `StudentResult.studentId` — **Encrypted** (AES-256-GCM, prefix `enc:v1:`)
- `StudentResult.imagePath` — **Encrypted** (same scheme)
- `ExamMetadata.extra` — JSON field storing `{ contribution: number, cloMap: string }`
- `CloPloMatrix.contribution` — 1-5 scale for CLO→PLO weight

### Encryption Scheme
Prisma middleware intercepts `create`/`update` on `StudentResult`:
```typescript
beforeCreate: encrypt(studentId, imagePath)
afterRead:    decrypt(studentId, imagePath)
```
Encrypted format: `enc:v1:{iv}:{authTag}:{ciphertext}` (base64-encoded components).

### Key Indexes
- `Course.createdById` — for user-specific course listings
- `CLO.[courseId, code, termId]` — unique per term
- `PLO.[programId, code, termId]` — unique per term

### Migration Rules
1. **Never** edit migration files after applied
2. **Never** delete migrations (breaks schema history)
3. **Always** test migrations on staging DB first
4. Use `prisma migrate deploy` in production (not `migrate dev`)

---

## 8. CURRENT STATE

### ✅ Working Features
- User authentication via LDAP + JWT cookies
- Course/CLO/PLO management
- OMR scan upload + async processing via BullMQ
- Real-time scan progress via SSE
- Manual result verification UI
- CLO/PLO analytics dashboard with Recharts
- Z-report generation (MÜDEK-compliant PDFs)
- Exam cover sheet generator
- User admin panel (role management)
- Dev DB browser (raw SQL + schema viewer)
- Dark/light theme toggle
- Role-based access control (instructor/admin/dev)

### 🚧 In Development
- Exam question bank management
- Multi-term comparison analytics
- Batch exam processing UI improvements

### ⚠️ AI AGENT — DO NOT TOUCH
- **Location**: `frontend/app/agent/`
- **Status**: Work in progress, partially implemented
- **Backend**: NOT yet connected
- **DO NOT** refactor, **DO NOT** add to sidebar navigation
- **DO NOT** add API endpoints for it without explicit instruction
- **Treat this entire folder as frozen**

### 🐛 Known Issues
- Backend logs show occasional Redis connection timeouts (non-critical, auto-reconnects)
- PDF export on Safari sometimes shows layout shifts (use Chrome for now)
- YOLO model occasionally misdetects bubbles on low-contrast scans (manual verification required)
- Handwriting OCR requires numbers to be written clearly inside the score boxes. TensorFlow CNN handles digit recognition.
- SSE connection drops on long-running scans (>5 min) — no reconnect logic yet  
  ⚠️ **DO NOT add reconnect logic to SSE without team discussion** — requires coordinated changes in both frontend `EventSource` and backend `scan-events` controller

---

## 9. COMMON TASKS

### Add a New API Endpoint
1. Define DTO in `src/dto/`:
```typescript
export class GetReportDto {
  @IsString() courseCode: string;
  @IsOptional() @IsString() termId?: string;
}
```

2. Add method to `AppService`:
```typescript
async generateReport(dto: GetReportDto) {
  const course = await this.prisma.course.findFirst({ where: { code: dto.courseCode } });
  if (!course) throw new NotFoundException('Course not found');
  // ... logic
  return { report: data };
}
```

3. Add controller route in `AppController`:
```typescript
@Post('reports')
@Roles('instructor', 'admin')
async getReport(@Body() dto: GetReportDto) {
  return this.appService.generateReport(dto);
}
```

4. Build + deploy:
```bash
npm run build
docker cp dist/app.service.js backend:/app/dist/app.service.js
docker cp dist/app.controller.js backend:/app/dist/app.controller.js
docker restart backend
```

5. Add to frontend `MudekApi` in `lib/api.ts`:
```typescript
static async getReport(courseCode: string, termId?: string) {
  return this.post('/api/reports', { courseCode, termId });
}
```

### Add a shadcn/ui Component
```bash
cd /var/www/Accredita-Full/frontend
npx shadcn@latest add <component-name>
```
Component appears in `components/ui/<component-name>.tsx`. Import and use:
```typescript
import { Button } from '@/components/ui/button';
<Button variant="outline">Click Me</Button>
```

### Add a New Dashboard Page
1. Create route file in `frontend/app/(dashboard)/my-page/page.tsx`:
```typescript
export default async function MyPage() {
  const data = await MudekApi.getMyData();
  return <div>My Page Content</div>;
}
```

2. Add navigation link in `components/sidebar.tsx`:
```typescript
{ href: '/my-page', label: 'My Page', icon: Icon, roles: ['admin', 'dev'] }
```

3. Add middleware protection in `frontend/middleware.ts` if role-restricted:
```typescript
if (pathname.startsWith('/my-page') && !['admin', 'dev'].includes(userRole)) {
  return NextResponse.redirect(new URL('/unauthorized', request.url));
}
```

### Add Prisma Model Field
1. Edit `backend/backend/prisma/schema.prisma`:
```prisma
model Course {
  id      Int    @id @default(autoincrement())
  code    String
  newField String? // Add this
  // ...
}
```

2. Create migration:
```bash
npx prisma migrate dev --name add_course_new_field
npx prisma generate
```

3. Update DTOs and service logic to use new field.

4. Build + redeploy backend.

---

## 10. WHAT TO AVOID

### ❌ Common Mistakes
1. **Editing backend code and expecting live reload** — Backend source is NOT volume-mounted. Must rebuild + docker cp + restart.

2. **Storing secrets in environment variables** — Use Docker secrets + `readSecret()` utility.

3. **Using `prisma.executeRaw()` for sensitive student data** — Encryption middleware won't work. Use Prisma queries.

4. **Hardcoding MÜDEK thresholds in multiple places** — Thresholds (60%) are in `getZReportData()` and `generateAssessmentReport()`. Change in one place risks inconsistency.

5. **Calling backend directly from frontend (e.g., `fetch('/api/...')`)** — Always use `MudekApi` client in `lib/api.ts`.

6. **Creating feature modules in NestJS** — This project uses a single `AppModule` + `AppService`. Don't split into modules unless explicitly refactoring.

7. **Assuming all users see all courses** — Courses are filtered by `createdById` (BlindID). Regular instructors only see their own courses.

8. **Exposing dev tools to production** — `/dev` routes must have `@Roles('dev')` guard. Never deploy with `SWAGGER_ENABLED=true` in prod.

9. **Ignoring Prisma transaction safety** — CLO/PLO calculations involve multiple DB queries. Use `$transaction([...])` for consistency.

10. **Modifying processed scan images** — Original scans are in `/app/uploads/`, processed outputs in `/app/processed/`. Never delete originals (needed for re-processing).

### 🗑️ Abandoned Technologies
- **TypeORM** — Replaced with Prisma (better type safety, simpler migrations)
- **Session-based auth** — Replaced with JWT cookies (stateless, scales better)
- **Manual OMR parsing** — Replaced with YOLOv8 (higher accuracy)
- **Separate frontend deployment** — Now runs in same Docker Compose stack (simpler networking)

### 🚫 False Assumptions
- "Backend changes are live after saving file" — **NO**, must rebuild + redeploy
- "JWT can be read from frontend JavaScript" — **NO**, it's httpOnly
- "All courses are public" — **NO**, filtered by creator BlindID
- "MÜDEK threshold is configurable per course" — **NO**, hardcoded at 60%
- "Redis is optional" — **NO**, BullMQ requires Redis for job queue

---

## 📝 NOTES
- **All API routes** have `/api/` prefix except auth routes (`/auth/login`, `/auth/logout`).
- **Static files** (processed scans) served from `/api/static/processed/`.
- **SSE endpoint** for real-time scan progress: `GET /api/scan-events?userId=<blindId>`.
- **Swagger docs** (dev only): `http://localhost:3000/api-docs` (basic auth: `admin` / secret).
- **Health check**: `GET /api/health` (public, no auth).
- **Database backups**: Automated via `scripts/backup.sh` (run daily via cron).

---

**Last updated**: 2026-04-06  
**Maintainer**: Beykoz University IT Department  
**Support**: Internal issue tracker (no public repo)
