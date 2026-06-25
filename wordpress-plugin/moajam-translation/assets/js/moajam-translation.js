(function () {
    'use strict';

    var STATUS_LABELS = {
        pending: 'في الانتظار',
        processing: 'قيد المعالجة',
        done: 'تم الإنجاز',
        failed: 'فشلت',
    };

    function renderJob(container, job) {
        var label = STATUS_LABELS[job.status] || job.status;
        var html = '<p><strong>رقم الطلب:</strong> ' + job.id + '</p>';
        html += '<p><strong>الحالة:</strong> <span class="moajam-translate-badge moajam-translate-badge-' + job.status + '">' + label + '</span></p>';

        if (job.status === 'failed' && job.error_message) {
            html += '<p class="moajam-translate-error">' + job.error_message + '</p>';
        }

        if (job.download_url) {
            html += '<p><a class="moajam-translate-btn" href="' + job.download_url + '" target="_blank" rel="noopener">تحميل الملف المترجم</a></p>';
        } else if (job.status !== 'failed') {
            html += '<p class="moajam-translate-hint">سيظهر زر التحميل هنا تلقائيًا عند اكتمال الترجمة.</p>';
        }

        container.innerHTML = html;
        container.hidden = false;
    }

    function renderError(container, message) {
        container.innerHTML = '<p class="moajam-translate-error">' + message + '</p>';
        container.hidden = false;
    }

    function post(action, body) {
        body.append('action', action);
        body.append('nonce', MoajamTranslate.nonce);
        return fetch(MoajamTranslate.ajaxUrl, { method: 'POST', body: body })
            .then(function (res) { return res.json(); });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var uploadForm = document.getElementById('moajam-translate-form');
        var uploadResult = document.getElementById('moajam-translate-upload-result');
        var statusForm = document.getElementById('moajam-translate-status-form');
        var statusResult = document.getElementById('moajam-translate-status-result');
        var jobIdInput = document.getElementById('moajam-translate-job-id');
        var pollTimer = null;

        function pollStatus(jobId) {
            clearInterval(pollTimer);
            var poll = function () {
                var body = new FormData();
                body.append('job_id', jobId);
                post('moajam_translate_check_status', body).then(function (res) {
                    if (!res.success) {
                        return;
                    }
                    renderJob(uploadResult, res.data);
                    if (res.data.status === 'done' || res.data.status === 'failed') {
                        clearInterval(pollTimer);
                    }
                });
            };
            poll();
            pollTimer = setInterval(poll, 5000);
        }

        if (uploadForm) {
            uploadForm.addEventListener('submit', function (e) {
                e.preventDefault();
                uploadResult.hidden = true;
                var body = new FormData(uploadForm);
                post('moajam_translate_create_job', body).then(function (res) {
                    if (!res.success) {
                        renderError(uploadResult, res.data.message || 'حدث خطأ غير متوقع');
                        return;
                    }
                    jobIdInput.value = res.data.job_id;
                    renderJob(uploadResult, { id: res.data.job_id, status: res.data.status });
                    pollStatus(res.data.job_id);
                }).catch(function () {
                    renderError(uploadResult, 'تعذر الاتصال بالخادم');
                });
            });
        }

        if (statusForm) {
            statusForm.addEventListener('submit', function (e) {
                e.preventDefault();
                statusResult.hidden = true;
                var body = new FormData(statusForm);
                post('moajam_translate_check_status', body).then(function (res) {
                    if (!res.success) {
                        renderError(statusResult, res.data.message || 'حدث خطأ غير متوقع');
                        return;
                    }
                    renderJob(statusResult, res.data);
                }).catch(function () {
                    renderError(statusResult, 'تعذر الاتصال بالخادم');
                });
            });
        }
    });
})();
