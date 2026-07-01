import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { Database, Search, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  type PdEcrInput,
  searchPdEcrHistory,
  uploadAndStageDocument,
} from "@/lib/pdEcrApi";
import {
  buildHistoryResult,
  fallbackHistoryModules,
  saveHistoryResult,
} from "./pdEcrState";

const defaultSearchText = "";

function buildSearchInput(query: string): PdEcrInput {
  return {
    dc_no: "PD-ECR-search",
    date: new Date().toISOString().slice(0, 10),
    customer_project: "PD-ECR Platform",
    reason: query,
    change_proposal: query,
    remarks: "AI Search historical PD-ECR cases",
  };
}

function HistoryToolPanel({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="enterprise-panel overflow-hidden">
      <header className="border-b border-slate-200 bg-slate-50/70 px-5 py-4">
        <p className="enterprise-section-title">{eyebrow}</p>
        <h2 className="mt-1 text-lg font-semibold text-slate-900">{title}</h2>
      </header>
      <div className="p-5">{children}</div>
    </section>
  );
}

export function PdEcrHistoryCase() {
  const navigate = useNavigate();
  const [searchText, setSearchText] = useState(defaultSearchText);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const historyMutation = useMutation({
    mutationFn: () => searchPdEcrHistory(buildSearchInput(searchText)),
    onSuccess: (response) => {
      const result = buildHistoryResult(response);
      saveHistoryResult(result);
      navigate({ to: "/pd-ecr/cases", search: { view: "similar" } });
    },
    onError: () => {
      saveHistoryResult({
        source: "history" as const,
        relatedCases: [],
        caseRows: [],
        modules: fallbackHistoryModules,
      });
      navigate({ to: "/pd-ecr/cases", search: { view: "similar" } });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadAndStageDocument(file),
    onSuccess: (staged) => {
      setUploadStatus(
        `OK ${staged.original_filename} 已解析，进入历史 PD-ECR 入库审核`,
      );
      navigate({
        to: "/pd-ecr/documents/$docId",
        params: { docId: staged.id },
      });
    },
    onError: (error: Error) => {
      setUploadStatus(`上传失败: ${error.message}`);
    },
  });

  const handleFileDrop = (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    const suffix = file.name.split(".").pop()?.toLowerCase();
    if (
      !suffix ||
      !["xlsx", "xls", "xlsm", "pdf", "docx", "doc"].includes(suffix)
    ) {
      setUploadStatus(
        "历史 PD-ECR 入库仅支持 .xlsx / .xls / .pdf / .docx 文件",
      );
      return;
    }
    setUploadStatus(`正在解析历史 PD-ECR 文件 ${file.name}...`);
    uploadMutation.mutate(file);
  };

  return (
    <div className="page-shell w-full min-w-0">
      <header className="enterprise-panel px-5 py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Database className="size-5 text-blue-700" />
              <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
                History Case
              </h1>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              Search historical PD-ECR cases and import historical source files.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            className="bg-white hover:border-blue-300 hover:bg-blue-50"
            onClick={() =>
              navigate({ to: "/pd-ecr/cases", search: { view: "all" } })
            }
          >
            All Cases
          </Button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1fr)_28rem]">
        <HistoryToolPanel eyebrow="AI Search" title="历史数据搜索">
          <div className="space-y-4">
            <textarea
              aria-label="AI Search"
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="输入变更原因、变更描述、零件号、客户项目等关键词..."
              className="min-h-48 w-full resize-y rounded-md border border-slate-300 bg-white px-4 py-3 text-sm leading-6 text-slate-900 shadow-none outline-none placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-blue-100 bg-blue-50 px-4 py-3">
              <p className="text-sm text-blue-800">
                Search 后会进入相似历史 CASE 列表页。
              </p>
              <Button
                type="button"
                onClick={() => historyMutation.mutate()}
                disabled={historyMutation.isPending}
                className="h-10 bg-blue-700 px-5 text-white hover:bg-blue-800"
              >
                <Search className="size-4" />
                {historyMutation.isPending ? "Searching" : "Search"}
              </Button>
            </div>
          </div>
        </HistoryToolPanel>

        <HistoryToolPanel eyebrow="Knowledge Import" title="导入历史 PD-ECR">
          <div className="space-y-3">
            <p className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs leading-5 text-sky-800">
              这里用于导入历史 PD-ECR
              档案，不用于当前新建变更附件。确认入库后，解析文本进入 RAG
              知识库。
            </p>
            <label
              className={`relative block rounded-lg border-2 border-dashed p-6 text-center transition cursor-pointer ${
                isDragging
                  ? "border-blue-500 bg-blue-50"
                  : "border-slate-300 bg-slate-50 hover:border-blue-400 hover:bg-blue-50/50"
              }`}
              onDragOver={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={(event) => {
                event.preventDefault();
                setIsDragging(false);
              }}
              onDrop={(event) => {
                event.preventDefault();
                setIsDragging(false);
                handleFileDrop(event.dataTransfer.files);
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls,.xlsm,.pdf,.docx,.doc"
                className="absolute inset-0 cursor-pointer opacity-0"
                onChange={(event) => handleFileDrop(event.target.files)}
              />
              {uploadMutation.isPending ? (
                <div className="flex items-center justify-center gap-2 text-blue-700">
                  <span className="inline-block size-4 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
                  <span className="text-sm font-semibold">
                    解析历史文件中...
                  </span>
                </div>
              ) : (
                <div className="flex items-center justify-center gap-3 text-slate-500">
                  <Upload className="size-5" />
                  <span className="text-sm">
                    拖拽历史文件到此处，或点击上传
                  </span>
                </div>
              )}
            </label>

            {uploadStatus ? (
              <p
                className={`text-xs ${
                  uploadStatus.startsWith("OK")
                    ? "text-green-700"
                    : uploadStatus.includes("失败")
                      ? "text-red-600"
                      : "text-blue-700"
                }`}
              >
                {uploadStatus}
              </p>
            ) : null}
          </div>
        </HistoryToolPanel>
      </div>
    </div>
  );
}
