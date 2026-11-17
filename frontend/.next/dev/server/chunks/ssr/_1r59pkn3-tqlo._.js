module.exports = [
"[project]/node_modules/next/dist/api/navigation.react-server.js [app-rsc] (ecmascript) <locals>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$client$2f$components$2f$navigation$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/client/components/navigation.react-server.js [app-rsc] (ecmascript)");
;
}),
"[project]/node_modules/next/dist/client/components/forbidden.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "forbidden", {
    enumerable: true,
    get: function() {
        return forbidden;
    }
});
const _httpaccessfallback = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/http-access-fallback/http-access-fallback.js [app-rsc] (ecmascript)");
// TODO: Add `forbidden` docs
/**
 * @experimental
 * This function allows you to render the [forbidden.js file](https://nextjs.org/docs/app/api-reference/file-conventions/forbidden)
 * within a route segment as well as inject a tag.
 *
 * `forbidden()` can be used in
 * [Server Components](https://nextjs.org/docs/app/building-your-application/rendering/server-components),
 * [Route Handlers](https://nextjs.org/docs/app/building-your-application/routing/route-handlers), and
 * [Server Actions](https://nextjs.org/docs/app/building-your-application/data-fetching/server-actions-and-mutations).
 *
 * Read more: [Next.js Docs: `forbidden`](https://nextjs.org/docs/app/api-reference/functions/forbidden)
 */ const DIGEST = `${_httpaccessfallback.HTTP_ERROR_FALLBACK_ERROR_CODE};403`;
function forbidden() {
    if ("TURBOPACK compile-time truthy", 1) {
        throw new Error(`\`forbidden()\` is experimental and only allowed to be enabled when \`experimental.authInterrupts\` is enabled.`);
    }
    const error = new Error(DIGEST);
    error.digest = DIGEST;
    throw error;
}
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/node_modules/next/dist/client/components/http-access-fallback/http-access-fallback.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
0 && (module.exports = {
    HTTPAccessErrorStatus: null,
    HTTP_ERROR_FALLBACK_ERROR_CODE: null,
    getAccessFallbackErrorTypeByStatus: null,
    getAccessFallbackHTTPStatus: null,
    isHTTPAccessFallbackError: null
});
function _export(target, all) {
    for(var name in all)Object.defineProperty(target, name, {
        enumerable: true,
        get: all[name]
    });
}
_export(exports, {
    HTTPAccessErrorStatus: function() {
        return HTTPAccessErrorStatus;
    },
    HTTP_ERROR_FALLBACK_ERROR_CODE: function() {
        return HTTP_ERROR_FALLBACK_ERROR_CODE;
    },
    getAccessFallbackErrorTypeByStatus: function() {
        return getAccessFallbackErrorTypeByStatus;
    },
    getAccessFallbackHTTPStatus: function() {
        return getAccessFallbackHTTPStatus;
    },
    isHTTPAccessFallbackError: function() {
        return isHTTPAccessFallbackError;
    }
});
const HTTPAccessErrorStatus = {
    NOT_FOUND: 404,
    FORBIDDEN: 403,
    UNAUTHORIZED: 401
};
const ALLOWED_CODES = new Set(Object.values(HTTPAccessErrorStatus));
const HTTP_ERROR_FALLBACK_ERROR_CODE = 'NEXT_HTTP_ERROR_FALLBACK';
function isHTTPAccessFallbackError(error) {
    if (typeof error !== 'object' || error === null || !('digest' in error) || typeof error.digest !== 'string') {
        return false;
    }
    const [prefix, httpStatus] = error.digest.split(';');
    return prefix === HTTP_ERROR_FALLBACK_ERROR_CODE && ALLOWED_CODES.has(Number(httpStatus));
}
function getAccessFallbackHTTPStatus(error) {
    const httpStatus = error.digest.split(';')[1];
    return Number(httpStatus);
}
function getAccessFallbackErrorTypeByStatus(status) {
    switch(status){
        case 401:
            return 'unauthorized';
        case 403:
            return 'forbidden';
        case 404:
            return 'not-found';
        default:
            return;
    }
}
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/node_modules/next/dist/client/components/is-next-router-error.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "isNextRouterError", {
    enumerable: true,
    get: function() {
        return isNextRouterError;
    }
});
const _httpaccessfallback = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/http-access-fallback/http-access-fallback.js [app-rsc] (ecmascript)");
const _redirecterror = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/redirect-error.js [app-rsc] (ecmascript)");
function isNextRouterError(error) {
    return (0, _redirecterror.isRedirectError)(error) || (0, _httpaccessfallback.isHTTPAccessFallbackError)(error);
}
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/node_modules/next/dist/client/components/navigation.react-server.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
0 && (module.exports = {
    ReadonlyURLSearchParams: null,
    RedirectType: null,
    forbidden: null,
    notFound: null,
    permanentRedirect: null,
    redirect: null,
    unauthorized: null,
    unstable_isUnrecognizedActionError: null,
    unstable_rethrow: null
});
function _export(target, all) {
    for(var name in all)Object.defineProperty(target, name, {
        enumerable: true,
        get: all[name]
    });
}
_export(exports, {
    ReadonlyURLSearchParams: function() {
        return _readonlyurlsearchparams.ReadonlyURLSearchParams;
    },
    RedirectType: function() {
        return RedirectType;
    },
    forbidden: function() {
        return _forbidden.forbidden;
    },
    notFound: function() {
        return _notfound.notFound;
    },
    permanentRedirect: function() {
        return _redirect.permanentRedirect;
    },
    redirect: function() {
        return _redirect.redirect;
    },
    unauthorized: function() {
        return _unauthorized.unauthorized;
    },
    unstable_isUnrecognizedActionError: function() {
        return unstable_isUnrecognizedActionError;
    },
    unstable_rethrow: function() {
        return _unstablerethrow.unstable_rethrow;
    }
});
const _readonlyurlsearchparams = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/readonly-url-search-params.js [app-rsc] (ecmascript)");
const _redirect = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/redirect.js [app-rsc] (ecmascript)");
const _notfound = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/not-found.js [app-rsc] (ecmascript)");
const _forbidden = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/forbidden.js [app-rsc] (ecmascript)");
const _unauthorized = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/unauthorized.js [app-rsc] (ecmascript)");
const _unstablerethrow = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/unstable-rethrow.js [app-rsc] (ecmascript)");
function unstable_isUnrecognizedActionError() {
    throw new Error('`unstable_isUnrecognizedActionError` can only be used on the client.');
}
const RedirectType = {
    push: 'push',
    replace: 'replace'
};
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/node_modules/next/dist/client/components/not-found.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "notFound", {
    enumerable: true,
    get: function() {
        return notFound;
    }
});
const _httpaccessfallback = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/http-access-fallback/http-access-fallback.js [app-rsc] (ecmascript)");
/**
 * This function allows you to render the [not-found.js file](https://nextjs.org/docs/app/api-reference/file-conventions/not-found)
 * within a route segment as well as inject a tag.
 *
 * `notFound()` can be used in
 * [Server Components](https://nextjs.org/docs/app/building-your-application/rendering/server-components),
 * [Route Handlers](https://nextjs.org/docs/app/building-your-application/routing/route-handlers), and
 * [Server Actions](https://nextjs.org/docs/app/building-your-application/data-fetching/server-actions-and-mutations).
 *
 * - In a Server Component, this will insert a `<meta name="robots" content="noindex" />` meta tag and set the status code to 404.
 * - In a Route Handler or Server Action, it will serve a 404 to the caller.
 *
 * Read more: [Next.js Docs: `notFound`](https://nextjs.org/docs/app/api-reference/functions/not-found)
 */ const DIGEST = `${_httpaccessfallback.HTTP_ERROR_FALLBACK_ERROR_CODE};404`;
function notFound() {
    const error = new Error(DIGEST);
    error.digest = DIGEST;
    throw error;
}
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/node_modules/next/dist/client/components/readonly-url-search-params.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

/**
 * ReadonlyURLSearchParams implementation shared between client and server.
 * This file is intentionally not marked as 'use client' or 'use server'
 * so it can be imported by both environments.
 */ /** @internal */ Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "ReadonlyURLSearchParams", {
    enumerable: true,
    get: function() {
        return ReadonlyURLSearchParams;
    }
});
class ReadonlyURLSearchParamsError extends Error {
    constructor(){
        super('Method unavailable on `ReadonlyURLSearchParams`. Read more: https://nextjs.org/docs/app/api-reference/functions/use-search-params#updating-searchparams');
    }
}
class ReadonlyURLSearchParams extends URLSearchParams {
    /** @deprecated Method unavailable on `ReadonlyURLSearchParams`. Read more: https://nextjs.org/docs/app/api-reference/functions/use-search-params#updating-searchparams */ append() {
        throw new ReadonlyURLSearchParamsError();
    }
    /** @deprecated Method unavailable on `ReadonlyURLSearchParams`. Read more: https://nextjs.org/docs/app/api-reference/functions/use-search-params#updating-searchparams */ delete() {
        throw new ReadonlyURLSearchParamsError();
    }
    /** @deprecated Method unavailable on `ReadonlyURLSearchParams`. Read more: https://nextjs.org/docs/app/api-reference/functions/use-search-params#updating-searchparams */ set() {
        throw new ReadonlyURLSearchParamsError();
    }
    /** @deprecated Method unavailable on `ReadonlyURLSearchParams`. Read more: https://nextjs.org/docs/app/api-reference/functions/use-search-params#updating-searchparams */ sort() {
        throw new ReadonlyURLSearchParamsError();
    }
}
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/node_modules/next/dist/client/components/redirect-error.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
0 && (module.exports = {
    REDIRECT_ERROR_CODE: null,
    isRedirectError: null
});
function _export(target, all) {
    for(var name in all)Object.defineProperty(target, name, {
        enumerable: true,
        get: all[name]
    });
}
_export(exports, {
    REDIRECT_ERROR_CODE: function() {
        return REDIRECT_ERROR_CODE;
    },
    isRedirectError: function() {
        return isRedirectError;
    }
});
const _redirectstatuscode = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/redirect-status-code.js [app-rsc] (ecmascript)");
const REDIRECT_ERROR_CODE = 'NEXT_REDIRECT';
function isRedirectError(error) {
    if (typeof error !== 'object' || error === null || !('digest' in error) || typeof error.digest !== 'string') {
        return false;
    }
    const digest = error.digest.split(';');
    const [errorCode, type] = digest;
    const destination = digest.slice(2, -2).join(';');
    const status = digest.at(-2);
    const statusCode = Number(status);
    return errorCode === REDIRECT_ERROR_CODE && (type === 'replace' || type === 'push') && typeof destination === 'string' && !isNaN(statusCode) && statusCode in _redirectstatuscode.RedirectStatusCode;
}
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/node_modules/next/dist/client/components/redirect-status-code.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "RedirectStatusCode", {
    enumerable: true,
    get: function() {
        return RedirectStatusCode;
    }
});
var RedirectStatusCode = /*#__PURE__*/ function(RedirectStatusCode) {
    RedirectStatusCode[RedirectStatusCode["SeeOther"] = 303] = "SeeOther";
    RedirectStatusCode[RedirectStatusCode["TemporaryRedirect"] = 307] = "TemporaryRedirect";
    RedirectStatusCode[RedirectStatusCode["PermanentRedirect"] = 308] = "PermanentRedirect";
    return RedirectStatusCode;
}({});
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/node_modules/next/dist/client/components/redirect.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
0 && (module.exports = {
    getRedirectError: null,
    getRedirectStatusCodeFromError: null,
    getRedirectTypeFromError: null,
    getURLFromRedirectError: null,
    permanentRedirect: null,
    redirect: null
});
function _export(target, all) {
    for(var name in all)Object.defineProperty(target, name, {
        enumerable: true,
        get: all[name]
    });
}
_export(exports, {
    getRedirectError: function() {
        return getRedirectError;
    },
    getRedirectStatusCodeFromError: function() {
        return getRedirectStatusCodeFromError;
    },
    getRedirectTypeFromError: function() {
        return getRedirectTypeFromError;
    },
    getURLFromRedirectError: function() {
        return getURLFromRedirectError;
    },
    permanentRedirect: function() {
        return permanentRedirect;
    },
    redirect: function() {
        return redirect;
    }
});
const _redirectstatuscode = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/redirect-status-code.js [app-rsc] (ecmascript)");
const _redirecterror = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/redirect-error.js [app-rsc] (ecmascript)");
const _serverasyncstorage = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/server-async-storage.js [app-rsc] (ecmascript)");
function getRedirectError(url, type, statusCode = _redirectstatuscode.RedirectStatusCode.TemporaryRedirect) {
    const error = new Error(_redirecterror.REDIRECT_ERROR_CODE);
    error.digest = `${_redirecterror.REDIRECT_ERROR_CODE};${type};${url};${statusCode};`;
    return error;
}
function redirect(/** The URL to redirect to */ url, type) {
    type ??= _serverasyncstorage.actionAsyncStorage?.getStore()?.isAction ? 'push' : 'replace';
    throw getRedirectError(url, type, _redirectstatuscode.RedirectStatusCode.TemporaryRedirect);
}
function permanentRedirect(/** The URL to redirect to */ url, type = 'replace') {
    throw getRedirectError(url, type, _redirectstatuscode.RedirectStatusCode.PermanentRedirect);
}
function getURLFromRedirectError(error) {
    if (!(0, _redirecterror.isRedirectError)(error)) return null;
    // Slices off the beginning of the digest that contains the code and the
    // separating ';'.
    return error.digest.split(';').slice(2, -2).join(';');
}
function getRedirectTypeFromError(error) {
    if (!(0, _redirecterror.isRedirectError)(error)) {
        throw new Error('Not a redirect error');
    }
    return error.digest.split(';', 2)[1];
}
function getRedirectStatusCodeFromError(error) {
    if (!(0, _redirecterror.isRedirectError)(error)) {
        throw new Error('Not a redirect error');
    }
    return Number(error.digest.split(';').at(-2));
}
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/node_modules/next/dist/client/components/server-async-storage.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

// Client-safe access to the server-only async-storage singletons. On the
// server these re-export the real storages; in the browser bundle this module
// is aliased to `./server-async-storage.browser` (see
// scripts/generate-browser-variant-aliases.mjs), which exports `undefined`
// stubs so the AsyncLocalStorage modules are never bundled into the client.
// Consumers must guard usage so the stubs are not dereferenced in the browser.
Object.defineProperty(exports, "__esModule", {
    value: true
});
0 && (module.exports = {
    actionAsyncStorage: null,
    workAsyncStorage: null,
    workUnitAsyncStorage: null
});
function _export(target, all) {
    for(var name in all)Object.defineProperty(target, name, {
        enumerable: true,
        get: all[name]
    });
}
_export(exports, {
    actionAsyncStorage: function() {
        return _actionasyncstorageexternal.actionAsyncStorage;
    },
    workAsyncStorage: function() {
        return _workasyncstorageexternal.workAsyncStorage;
    },
    workUnitAsyncStorage: function() {
        return _workunitasyncstorageexternal.workUnitAsyncStorage;
    }
});
const _actionasyncstorageexternal = __turbopack_context__.r("[externals]/next/dist/server/app-render/action-async-storage.external.js [external] (next/dist/server/app-render/action-async-storage.external.js, cjs)");
const _workasyncstorageexternal = __turbopack_context__.r("[externals]/next/dist/server/app-render/work-async-storage.external.js [external] (next/dist/server/app-render/work-async-storage.external.js, cjs)");
const _workunitasyncstorageexternal = __turbopack_context__.r("[externals]/next/dist/server/app-render/work-unit-async-storage.external.js [external] (next/dist/server/app-render/work-unit-async-storage.external.js, cjs)");
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/node_modules/next/dist/client/components/unauthorized.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "unauthorized", {
    enumerable: true,
    get: function() {
        return unauthorized;
    }
});
const _httpaccessfallback = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/http-access-fallback/http-access-fallback.js [app-rsc] (ecmascript)");
// TODO: Add `unauthorized` docs
/**
 * @experimental
 * This function allows you to render the [unauthorized.js file](https://nextjs.org/docs/app/api-reference/file-conventions/unauthorized)
 * within a route segment as well as inject a tag.
 *
 * `unauthorized()` can be used in
 * [Server Components](https://nextjs.org/docs/app/building-your-application/rendering/server-components),
 * [Route Handlers](https://nextjs.org/docs/app/building-your-application/routing/route-handlers), and
 * [Server Actions](https://nextjs.org/docs/app/building-your-application/data-fetching/server-actions-and-mutations).
 *
 *
 * Read more: [Next.js Docs: `unauthorized`](https://nextjs.org/docs/app/api-reference/functions/unauthorized)
 */ const DIGEST = `${_httpaccessfallback.HTTP_ERROR_FALLBACK_ERROR_CODE};401`;
function unauthorized() {
    if ("TURBOPACK compile-time truthy", 1) {
        throw new Error(`\`unauthorized()\` is experimental and only allowed to be used when \`experimental.authInterrupts\` is enabled.`);
    }
    const error = new Error(DIGEST);
    error.digest = DIGEST;
    throw error;
}
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/node_modules/next/dist/client/components/unstable-rethrow.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, "unstable_rethrow", {
    enumerable: true,
    get: function() {
        return unstable_rethrow;
    }
});
const _dynamicrenderingutils = __turbopack_context__.r("[project]/node_modules/next/dist/server/dynamic-rendering-utils.js [app-rsc] (ecmascript)");
const _bailouttocsr = __turbopack_context__.r("[project]/node_modules/next/dist/shared/lib/lazy-dynamic/bailout-to-csr.js [app-rsc] (ecmascript)");
const _isnextroutererror = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/is-next-router-error.js [app-rsc] (ecmascript)");
const _dynamicrendering = __turbopack_context__.r("[project]/node_modules/next/dist/server/app-render/dynamic-rendering.js [app-rsc] (ecmascript)");
const _hooksservercontext = __turbopack_context__.r("[project]/node_modules/next/dist/client/components/hooks-server-context.js [app-rsc] (ecmascript)");
function unstable_rethrow(error) {
    if ((0, _isnextroutererror.isNextRouterError)(error) || (0, _bailouttocsr.isBailoutToCSRError)(error) || (0, _hooksservercontext.isDynamicServerError)(error) || (0, _dynamicrenderingutils.isHangingPromiseRejectionError)(error) || (0, _dynamicrendering.isPrerenderInterruptedError)(error)) {
        throw error;
    }
    if (error instanceof Error && 'cause' in error) {
        unstable_rethrow(error.cause);
    }
}
if ((typeof exports.default === 'function' || typeof exports.default === 'object' && exports.default !== null) && typeof exports.default.__esModule === 'undefined') {
    Object.defineProperty(exports.default, '__esModule', {
        value: true
    });
    Object.assign(exports.default, exports);
    module.exports = exports.default;
}
}),
"[project]/node_modules/next/dist/shared/lib/lazy-dynamic/bailout-to-csr.js [app-rsc] (ecmascript)", ((__turbopack_context__, module, exports) => {
"use strict";

// This has to be a shared module which is shared between client component error boundary and dynamic component
Object.defineProperty(exports, "__esModule", {
    value: true
});
0 && (module.exports = {
    BailoutToCSRError: null,
    isBailoutToCSRError: null
});
function _export(target, all) {
    for(var name in all)Object.defineProperty(target, name, {
        enumerable: true,
        get: all[name]
    });
}
_export(exports, {
    BailoutToCSRError: function() {
        return BailoutToCSRError;
    },
    isBailoutToCSRError: function() {
        return isBailoutToCSRError;
    }
});
const BAILOUT_TO_CSR = 'BAILOUT_TO_CLIENT_SIDE_RENDERING';
class BailoutToCSRError extends Error {
    constructor(reason){
        super(`Bail out to client-side rendering: ${reason}`), this.reason = reason, this.digest = BAILOUT_TO_CSR;
    }
}
function isBailoutToCSRError(err) {
    if (typeof err !== 'object' || err === null || !('digest' in err)) {
        return false;
    }
    return err.digest === BAILOUT_TO_CSR;
}
}),
"[project]/src/app/lawyer/(lawyer)/layout.tsx [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>LawyerLayout
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-jsx-dev-runtime.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$api$2f$navigation$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/node_modules/next/dist/api/navigation.react-server.js [app-rsc] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$client$2f$components$2f$navigation$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/client/components/navigation.react-server.js [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$lawyer$2f$LawyerShell$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/components/lawyer/LawyerShell.tsx [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/api/lawyer.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$language$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/language.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$session$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/session.ts [app-rsc] (ecmascript)");
;
;
;
;
;
;
async function LawyerLayout({ children }) {
    const session = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$session$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getSession"])();
    if (!session) (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$client$2f$components$2f$navigation$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["redirect"])("/lawyer/login");
    if (session.role !== "lawyer") (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$client$2f$components$2f$navigation$2e$react$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["redirect"])("/client/dashboard");
    const language = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$language$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getLanguage"])();
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$jsx$2d$dev$2d$runtime$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["jsxDEV"])(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$lawyer$2f$LawyerShell$2e$tsx__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["LawyerShell"], {
        language: language,
        profile: (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["getLawyerProfile"])(),
        matterCount: (0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$api$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["listMatters"])().length,
        children: children
    }, void 0, false, {
        fileName: "[project]/src/app/lawyer/(lawyer)/layout.tsx",
        lineNumber: 17,
        columnNumber: 5
    }, this);
}
}),
"[project]/src/app/lawyer/(lawyer)/layout.tsx [app-rsc] (ecmascript, Next.js Server Component)", (function(__turbopack_context__){

__turbopack_context__.n(__turbopack_context__.i("[project]/src/app/lawyer/(lawyer)/layout.tsx [app-rsc] (ecmascript)"));
}),
"[project]/src/components/lawyer/LawyerShell.tsx [app-rsc] (client reference proxy)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LawyerShell",
    ()=>LawyerShell
]);
// This file is generated by next-core EcmascriptClientReferenceModule.
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/dist/server/route-modules/app-page/vendored/rsc/react-server-dom-turbopack-server.js [app-rsc] (ecmascript)");
;
const LawyerShell = (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$dist$2f$server$2f$route$2d$modules$2f$app$2d$page$2f$vendored$2f$rsc$2f$react$2d$server$2d$dom$2d$turbopack$2d$server$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["registerClientReference"])(function() {
    throw new Error("Attempted to call LawyerShell() from the server but LawyerShell is on the client. It's not possible to invoke a client function from the server, it can only be rendered as a Component or passed to props of a Client Component.");
}, "[project]/src/components/lawyer/LawyerShell.tsx", "LawyerShell");
}),
"[project]/src/components/lawyer/LawyerShell.tsx [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$lawyer$2f$LawyerShell$2e$tsx__$5b$app$2d$rsc$5d$__$28$client__reference__proxy$29$__ = __turbopack_context__.i("[project]/src/components/lawyer/LawyerShell.tsx [app-rsc] (client reference proxy)");
;
__turbopack_context__.n(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$components$2f$lawyer$2f$LawyerShell$2e$tsx__$5b$app$2d$rsc$5d$__$28$client__reference__proxy$29$__);
}),
"[project]/src/lib/api/lawyer.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "addDocument",
    ()=>addDocument,
    "addHearing",
    ()=>addHearing,
    "addHearingNote",
    ()=>addHearingNote,
    "approveHearingSummary",
    ()=>approveHearingSummary,
    "createClient",
    ()=>createClient,
    "createMatter",
    ()=>createMatter,
    "downloadHearingSummary",
    ()=>downloadHearingSummary,
    "getCase",
    ()=>getCase,
    "getClientDetail",
    ()=>getClientDetail,
    "getHearingSummary",
    ()=>getHearingSummary,
    "getLawyerProfile",
    ()=>getLawyerProfile,
    "getLawyerStats",
    ()=>getLawyerStats,
    "getRecentActivity",
    ()=>getRecentActivity,
    "getRecentMatters",
    ()=>getRecentMatters,
    "listCaseTypes",
    ()=>listCaseTypes,
    "listClients",
    ()=>listClients,
    "listCourts",
    ()=>listCourts,
    "listDocuments",
    ()=>listDocuments,
    "listHearings",
    ()=>listHearings,
    "listMatters",
    ()=>listMatters,
    "resetClientPassword",
    ()=>resetClientPassword,
    "saveHearingSummaryVersion",
    ()=>saveHearingSummaryVersion,
    "setCaseStage",
    ()=>setCaseStage,
    "setDocumentStatus",
    ()=>setDocumentStatus
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$documents$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/documents.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$client$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/mock/client.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$hearingSummaries$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/mock/hearingSummaries.ts [app-rsc] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/src/lib/mock/lawyer.ts [app-rsc] (ecmascript)");
;
;
;
;
function listMatters() {
    return [
        ...__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["matters"]
    ];
}
function getCase(caseId) {
    return __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["matters"].find((matter)=>matter.id === caseId) ?? null;
}
function setCaseStage(caseId, stageId) {
    const matter = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["matters"].find((item)=>item.id === caseId);
    if (!matter || matter.status === "closed" || !matter.stages.some((stage)=>stage.id === stageId)) {
        return false;
    }
    matter.currentStageId = stageId;
    return true;
}
function isValidDate(date) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
    const parsed = new Date(`${date}T00:00:00Z`);
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === date;
}
function listHearings(caseId) {
    return [
        ...__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hearings"][caseId] ?? []
    ].sort((a, b)=>a.number - b.number);
}
function summaryVersionsFor(hearing) {
    const existing = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$hearingSummaries$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hearingSummaryVersions"][hearing.id];
    if (existing) return existing;
    const seed = {
        id: `summary-${hearing.id}-v1`,
        version: 1,
        createdAt: `${hearing.date}T18:00:00.000Z`,
        editedBy: {
            en: "AI draft",
            bn: "এআই খসড়া"
        },
        sections: structuredClone(__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$hearingSummaries$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hearingSummarySections"])
    };
    __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$hearingSummaries$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hearingSummaryVersions"][hearing.id] = [
        seed
    ];
    return __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$hearingSummaries$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hearingSummaryVersions"][hearing.id];
}
function buildHearingSummary(matter, hearing) {
    const versions = summaryVersionsFor(hearing);
    const latest = versions[versions.length - 1];
    return {
        caseId: matter.id,
        hearingId: hearing.id,
        hearingNumber: hearing.number,
        hearingDate: hearing.date,
        court: hearing.court,
        matterTitle: matter.title,
        clientName: matter.clientName,
        status: hearing.summaryStatus,
        version: latest.version,
        sections: latest.sections,
        versions: [
            ...versions
        ]
    };
}
function summaryPublishedOn() {
    const now = new Date();
    return {
        en: new Intl.DateTimeFormat("en-GB", {
            day: "2-digit",
            month: "short",
            year: "numeric",
            timeZone: "UTC"
        }).format(now),
        bn: new Intl.DateTimeFormat("bn-BD", {
            day: "2-digit",
            month: "short",
            year: "numeric",
            timeZone: "UTC"
        }).format(now)
    };
}
function getHearingSummary(caseId, hearingId) {
    const matter = getCase(caseId);
    const hearing = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hearings"][caseId]?.find((item)=>item.id === hearingId);
    if (!matter || !hearing) return null;
    if (hearing.summaryStatus !== "draft_ready" && hearing.summaryStatus !== "approved") {
        return null;
    }
    return buildHearingSummary(matter, hearing);
}
function saveHearingSummaryVersion(caseId, hearingId, sections) {
    const matter = getCase(caseId);
    const hearing = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hearings"][caseId]?.find((item)=>item.id === hearingId);
    if (!matter || !hearing) return null;
    if (hearing.summaryStatus !== "draft_ready" && hearing.summaryStatus !== "approved") {
        return null;
    }
    if (sections.length === 0 || sections.some((section)=>section.claims.length === 0)) {
        return null;
    }
    const versions = summaryVersionsFor(hearing);
    const version = Math.max(0, ...versions.map((item)=>item.version)) + 1;
    versions.push({
        id: globalThis.crypto.randomUUID(),
        version,
        createdAt: new Date().toISOString(),
        editedBy: getLawyerProfile().name,
        sections: structuredClone(sections)
    });
    hearing.summaryStatus = "draft_ready";
    const clientSummaryId = `summary-${hearing.id}`;
    const clientIndex = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$client$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["storedSummaries"].findIndex((summary)=>summary.id === clientSummaryId);
    if (clientIndex >= 0) __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$client$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["storedSummaries"].splice(clientIndex, 1);
    return buildHearingSummary(matter, hearing);
}
function approveHearingSummary(caseId, hearingId) {
    const matter = getCase(caseId);
    const hearing = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hearings"][caseId]?.find((item)=>item.id === hearingId);
    if (!matter || !hearing) return null;
    if (hearing.summaryStatus !== "draft_ready" && hearing.summaryStatus !== "approved") {
        return null;
    }
    const versions = summaryVersionsFor(hearing);
    const latest = versions[versions.length - 1];
    const keyNote = latest.sections.find((section)=>section.id === "keyNotes")?.claims[0];
    const excerpt = keyNote?.text ?? {
        en: `The summary for hearing ${hearing.number} is ready.`,
        bn: `শুনানি ${hearing.number} সারসংক্ষেপ প্রস্তুত।`
    };
    const entry = {
        id: `summary-${hearing.id}`,
        caseId: matter.id,
        title: {
            en: `Hearing ${hearing.number} summary`,
            bn: `শুনানি ${hearing.number} সারসংক্ষেপ`
        },
        excerpt,
        publishedOn: summaryPublishedOn()
    };
    const clientIndex = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$client$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["storedSummaries"].findIndex((summary)=>summary.id === entry.id);
    if (clientIndex >= 0) {
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$client$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["storedSummaries"][clientIndex] = {
            ...entry,
            status: "approved"
        };
    } else {
        __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$client$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["storedSummaries"].unshift({
            ...entry,
            status: "approved"
        });
    }
    hearing.summaryStatus = "approved";
    return buildHearingSummary(matter, hearing);
}
function downloadHearingSummary() {
    return {
        status: "NOT_CONFIGURED"
    };
}
function addHearing(caseId, input) {
    const matter = getCase(caseId);
    const note = input.note.trim();
    if (!matter || matter.status === "closed") return null;
    if (!isValidDate(input.date) || !note) return null;
    const caseHearings = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hearings"][caseId] ?? [];
    const hearing = {
        id: globalThis.crypto.randomUUID(),
        number: Math.max(0, ...caseHearings.map((item)=>item.number)) + 1,
        date: input.date,
        court: matter.court,
        notes: [
            {
                id: globalThis.crypto.randomUUID(),
                text: note
            }
        ],
        summaryStatus: "none"
    };
    __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hearings"][caseId] = [
        ...caseHearings,
        hearing
    ];
    matter.hearingNumber = hearing.number;
    return hearing;
}
function addHearingNote(caseId, hearingId, text) {
    const matter = getCase(caseId);
    const hearing = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hearings"][caseId]?.find((item)=>item.id === hearingId);
    const note = text.trim();
    if (!matter || matter.status === "closed" || !hearing || !note) return null;
    hearing.notes.push({
        id: globalThis.crypto.randomUUID(),
        text: note
    });
    return hearing;
}
function listDocuments(caseId) {
    return [
        ...__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["documents"][caseId] ?? []
    ];
}
function addDocument(caseId, input) {
    const matter = getCase(caseId);
    const belongsToCase = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["hearings"][caseId]?.some((hearing)=>hearing.id === input.hearingId);
    if (!matter || matter.status === "closed" || !belongsToCase) return null;
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$documents$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["isAllowedDocument"])(input.name, input.mimeType)) return null;
    if (!Number.isInteger(input.size) || input.size <= 0 || input.size > __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$documents$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["MAX_DOCUMENT_BYTES"]) {
        return null;
    }
    const document = {
        id: globalThis.crypto.randomUUID(),
        hearingId: input.hearingId,
        name: input.name,
        size: input.size,
        mimeType: input.mimeType,
        status: "processing"
    };
    __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["documents"][caseId] = [
        ...__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["documents"][caseId] ?? [],
        document
    ];
    return document;
}
function setDocumentStatus(caseId, documentId, status) {
    if (status !== "processing" && status !== "ready" && status !== "failed") {
        return false;
    }
    const document = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["documents"][caseId]?.find((item)=>item.id === documentId);
    if (!document) return false;
    document.status = status;
    return true;
}
function listClients() {
    return __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["clients"].map((client)=>({
            ...client,
            caseCount: __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["matters"].filter((matter)=>matter.clientId === client.id).length
        }));
}
function getClientDetail(clientId) {
    const client = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["clients"].find((item)=>item.id === clientId);
    if (!client) return null;
    return {
        ...client,
        cases: __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["matters"].filter((matter)=>matter.clientId === clientId)
    };
}
function createClient(input) {
    const name = input.name.trim();
    const phone = input.phone.trim();
    const email = input.email.trim();
    if (!name || !phone || !/\S+@\S+\.\S+/.test(email)) return null;
    const clientId = `CL-${Math.floor(1000 + Math.random() * 9000)}-BD`;
    const password = globalThis.crypto.randomUUID().replace(/-/g, "").slice(0, 8);
    __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["clients"].unshift({
        id: clientId,
        name: {
            en: name,
            bn: name
        },
        phone,
        email
    });
    return {
        name,
        clientId,
        password
    };
}
function resetClientPassword() {
    return {
        status: "NOT_CONFIGURED"
    };
}
function createMatter(input) {
    const client = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["clients"].find((item)=>item.id === input.clientId);
    const court = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["courts"].find((item)=>item.en === input.court);
    const caseType = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["caseTypes"].find((item)=>item.en === input.caseType);
    const title = input.title.trim();
    if (!client || !court || !caseType || !title) return null;
    const matter = {
        id: `LC-${Math.floor(10000 + Math.random() * 90000)}`,
        title: {
            en: title,
            bn: title
        },
        clientId: client.id,
        clientName: client.name,
        court,
        caseType,
        hearingNumber: 1,
        status: "active",
        stages: __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["matterStages"].map((stage)=>({
                ...stage
            })),
        currentStageId: "filed"
    };
    __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["matters"].unshift(matter);
    return matter;
}
function getRecentMatters(limit = 3) {
    return __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["matters"].filter((matter)=>matter.status === "active").slice(0, limit);
}
function getLawyerStats() {
    const active = __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["matters"].filter((matter)=>matter.status === "active");
    const next = active.filter((matter)=>matter.nextHearing).sort((a, b)=>(a.nextHearing?.day ?? 0) - (b.nextHearing?.day ?? 0))[0];
    return {
        activeCases: active.length,
        totalMatters: __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["matters"].length,
        totalClients: __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["clients"].length,
        nextHearing: next?.nextHearing ? {
            day: next.nextHearing.day,
            month: next.nextHearing.month,
            matterTitle: next.title
        } : null
    };
}
function getRecentActivity() {
    return [
        ...__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["activities"]
    ];
}
function getLawyerProfile() {
    return __TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["lawyerProfile"];
}
function listCourts() {
    return [
        ...__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["courts"]
    ];
}
function listCaseTypes() {
    return [
        ...__TURBOPACK__imported__module__$5b$project$5d2f$src$2f$lib$2f$mock$2f$lawyer$2e$ts__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["caseTypes"]
    ];
}
}),
"[project]/src/lib/documents.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "MAX_DOCUMENT_BYTES",
    ()=>MAX_DOCUMENT_BYTES,
    "isAllowedDocument",
    ()=>isAllowedDocument
]);
const MAX_DOCUMENT_BYTES = 20 * 1024 * 1024;
const ALLOWED_EXTENSION = /\.(pdf|png|jpe?g|gif|webp|bmp|tiff?)$/i;
function isAllowedDocument(name, mimeType) {
    if (mimeType === "application/pdf" || mimeType.startsWith("image/")) {
        return true;
    }
    return !mimeType && ALLOWED_EXTENSION.test(name);
}
}),
"[project]/src/lib/mock/client.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "clientCase",
    ()=>clientCase,
    "clientProfile",
    ()=>clientProfile,
    "storedSummaries",
    ()=>storedSummaries
]);
const clientProfile = {
    name: {
        en: "Fahim Rahman",
        bn: "ফাহিম রহমান"
    }
};
const clientCase = {
    id: "LC-24018",
    title: {
        en: "Rahman vs. Karim",
        bn: "রহমান বনাম করিম"
    },
    statusLabel: {
        en: "Active",
        bn: "সক্রিয়"
    },
    caseType: {
        en: "Property dispute",
        bn: "সম্পত্তি বিরোধ"
    },
    court: {
        en: "Dhaka District Court",
        bn: "ঢাকা জেলা আদালত"
    },
    hearingNumber: 3,
    stages: [
        {
            id: "filed",
            label: {
                en: "Case filed",
                bn: "মামলা দায়ের"
            },
            note: {
                en: "12 Sep",
                bn: "১২ সেপ্টেম্বর"
            },
            state: "complete"
        },
        {
            id: "notice",
            label: {
                en: "Notice served",
                bn: "নোটিশ জারি"
            },
            note: {
                en: "28 Sep",
                bn: "২৮ সেপ্টেম্বর"
            },
            state: "complete"
        },
        {
            id: "evidence",
            label: {
                en: "Evidence",
                bn: "সাক্ষ্য"
            },
            note: {
                en: "In progress",
                bn: "চলমান"
            },
            state: "current"
        },
        {
            id: "arguments",
            label: {
                en: "Arguments",
                bn: "যুক্তিতর্ক"
            },
            note: {
                en: "Upcoming",
                bn: "আসন্ন"
            },
            state: "upcoming"
        },
        {
            id: "decision",
            label: {
                en: "Decision",
                bn: "রায়"
            },
            note: {
                en: "Upcoming",
                bn: "আসন্ন"
            },
            state: "upcoming"
        }
    ],
    nextHearing: {
        day: 17,
        month: {
            en: "JAN",
            bn: "জানু"
        },
        year: 2025,
        place: {
            en: "Courtroom 4, Dhaka District Court",
            bn: "আদালতকক্ষ ৪, ঢাকা জেলা আদালত"
        },
        dateLabel: {
            en: "Friday at 10:30 AM",
            bn: "শুক্রবার সকাল ১০:৩০"
        }
    },
    lawyer: {
        name: {
            en: "Farhana Ahmed",
            bn: "ফারহানা আহমেদ"
        },
        firm: {
            en: "Rahman & Associates",
            bn: "রহমান অ্যান্ড অ্যাসোসিয়েটস"
        },
        phone: "+880 1711-000000",
        email: "farhana@rahmanlaw.bd"
    },
    documents: [
        {
            id: "doc-petition",
            format: "PDF",
            name: {
                en: "Petition_Copy.pdf",
                bn: "আবেদনের কপি"
            },
            size: {
                en: "2.4 MB",
                bn: "২.৪ এমবি"
            },
            sharedOn: {
                en: "12 Sep 2024",
                bn: "১২ সেপ্টেম্বর ২০২৪"
            }
        },
        {
            id: "doc-order",
            format: "PDF",
            name: {
                en: "Court_Order_02.pdf",
                bn: "আদালতের আদেশ ০২"
            },
            size: {
                en: "1.1 MB",
                bn: "১.১ এমবি"
            },
            sharedOn: {
                en: "21 Nov 2024",
                bn: "২১ নভেম্বর ২০২৪"
            }
        },
        {
            id: "doc-witness",
            format: "PDF",
            name: {
                en: "Witness_Statement.pdf",
                bn: "সাক্ষীর বিবৃতি"
            },
            size: {
                en: "3.8 MB",
                bn: "৩.৮ এমবি"
            },
            sharedOn: {
                en: "10 Jan 2025",
                bn: "১০ জানুয়ারি ২০২৫"
            }
        }
    ]
};
const storedSummaries = [
    {
        id: "summary-h-24018-3",
        title: {
            en: "What happened at hearing 3",
            bn: "শুনানি ৩-এ কী হয়েছে"
        },
        excerpt: {
            en: "The court heard the first witness. The next hearing is on 17 January.",
            bn: "আদালত প্রথম সাক্ষীর বক্তব্য শুনেছেন। পরবর্তী শুনানি ১৭ জানুয়ারি।"
        },
        publishedOn: {
            en: "15 Jan 2025",
            bn: "১৫ জানুয়ারি ২০২৫"
        },
        status: "approved",
        sections: [
            {
                id: "keyNotes",
                text: {
                    en: "The court heard the first witness. The hearing record asks for the original deed next time.",
                    bn: "আদালত প্রথম সাক্ষীর বক্তব্য শুনেছেন। পরবর্তী শুনানিতে মূল দলিল আনার কথা রেকর্ডে বলা হয়েছে।"
                }
            },
            {
                id: "laws",
                text: {
                    en: "No legal question was decided at this hearing. Your lawyer will explain any legal point when it matters.",
                    bn: "এই শুনানিতে কোনো আইনি প্রশ্নের সিদ্ধান্ত হয়নি। কোনো আইনি বিষয় গুরুত্বপূর্ণ হলে আপনার আইনজীবী তা ব্যাখ্যা করবেন।"
                }
            },
            {
                id: "risks",
                text: {
                    en: "The other side may question the documents you rely on. Your lawyer is preparing for that.",
                    bn: "আপনি যে নথির ওপর নির্ভর করছেন, বিরোধী পক্ষ তা নিয়ে প্রশ্ন তুলতে পারে। আপনার আইনজীবী এর জন্য প্রস্তুতি নিচ্ছেন।"
                }
            },
            {
                id: "rights",
                text: {
                    en: "You have the right to be told what happened and to ask your lawyer questions.",
                    bn: "কী হয়েছে তা জানার এবং আপনার আইনজীবীকে প্রশ্ন করার অধিকার আপনার আছে।"
                }
            },
            {
                id: "notes",
                text: {
                    en: "This is a short update, not the full court record. Your lawyer can explain more.",
                    bn: "এটি একটি সংক্ষিপ্ত আপডেট, সম্পূর্ণ আদালতের রেকর্ড নয়। আপনার আইনজীবী আরও ব্যাখ্যা করতে পারেন।"
                }
            },
            {
                id: "nextSteps",
                text: {
                    en: "Bring the original deed to your lawyer before the next hearing.",
                    bn: "পরবর্তী শুনানির আগে মূল দলিল আপনার আইনজীবীর কাছে আনুন।"
                }
            }
        ]
    },
    {
        id: "summary-documents",
        title: {
            en: "New documents added",
            bn: "নতুন নথি যোগ হয়েছে"
        },
        excerpt: {
            en: "Your lawyer added the court order and a witness statement to your case.",
            bn: "আপনার আইনজীবী আদালতের আদেশ ও সাক্ষীর বিবৃতি মামলায় যোগ করেছেন।"
        },
        publishedOn: {
            en: "10 Jan 2025",
            bn: "১০ জানুয়ারি ২০২৫"
        },
        status: "approved",
        sections: [
            {
                id: "keyNotes",
                text: {
                    en: "Your lawyer added a court order and a witness statement to your case file.",
                    bn: "আপনার আইনজীবী মামলার ফাইলে একটি আদালতের আদেশ ও একটি সাক্ষীর বিবৃতি যোগ করেছেন।"
                }
            },
            {
                id: "laws",
                text: {
                    en: "These documents are part of the case record. Your lawyer can explain what they mean.",
                    bn: "এই নথিগুলো মামলার রেকর্ডের অংশ। এগুলোর অর্থ আপনার আইনজীবী ব্যাখ্যা করতে পারেন।"
                }
            },
            {
                id: "risks",
                text: {
                    en: "The other side can read documents shared with the court. Do not put private information in the case file.",
                    bn: "আদালতে শেয়ার করা নথি বিরোধী পক্ষ পড়তে পারে। মামলার ফাইলে ব্যক্তিগত তথ্য দেবেন না।"
                }
            },
            {
                id: "rights",
                text: {
                    en: "You can ask your lawyer to show you the documents added to your case.",
                    bn: "আপনার মামলায় যোগ করা নথি দেখতে আপনার আইনজীবীকে বলতে পারেন।"
                }
            },
            {
                id: "notes",
                text: {
                    en: "This update only lists new documents. It does not describe every paper in your case.",
                    bn: "এই আপডেটে শুধু নতুন নথির তালিকা আছে। আপনার মামলার সব কাগজ এতে বর্ণনা করা হয়নি।"
                }
            },
            {
                id: "nextSteps",
                text: {
                    en: "Read the new documents if you can, and note any questions for your lawyer.",
                    bn: "সম্ভব হলে নতুন নথিগুলো পড়ুন এবং আপনার আইনজীবীর জন্য প্রশ্ন লিখে রাখুন।"
                }
            }
        ]
    },
    {
        id: "summary-h-24018-2",
        title: {
            en: "What happened at hearing 2",
            bn: "শুনানি ২-এ কী হয়েছে"
        },
        excerpt: {
            en: "The court framed the issues for trial. Two issues were deferred.",
            bn: "আদালত বিচারের জন্য বিষয়গুলো নির্ধারণ করেছেন। দুটি বিষয় পরবর্তী তারিখে রাখা হয়েছে।"
        },
        publishedOn: {
            en: "22 Nov 2024",
            bn: "২২ নভেম্বর ২০২৪"
        },
        status: "approved",
        sections: [
            {
                id: "keyNotes",
                text: {
                    en: "The court listed the issues to decide at trial. Some issues were left for a later date.",
                    bn: "আদালত বিচারে সিদ্ধান্তের বিষয়গুলো তালিকাভুক্ত করেছেন। কিছু বিষয় পরবর্তী তারিখের জন্য রাখা হয়েছে।"
                }
            },
            {
                id: "laws",
                text: {
                    en: "The issues are based on the claims and documents filed. No legal provision is shared in this update.",
                    bn: "বিষয়গুলো দায়ের করা দাবি ও নথির ওপর ভিত্তি করে। এই আপডেটে কোনো আইনি ধারা শেয়ার করা হয়নি।"
                }
            },
            {
                id: "risks",
                text: {
                    en: "More issues may be added later, so the case can take longer.",
                    bn: "পরে আরও বিষয় যোগ হতে পারে, তাই মামলা দীর্ঘ হতে পারে।"
                }
            },
            {
                id: "rights",
                text: {
                    en: "You can ask your lawyer to explain each issue and what it means for you.",
                    bn: "প্রতিটি বিষয় এবং এর অর্থ আপনার জন্য কী, তা আপনার আইনজীবীকে জিজ্ঞাসা করতে পারেন।"
                }
            },
            {
                id: "notes",
                text: {
                    en: "This update is a summary only. It is not the court's full order.",
                    bn: "এই আপডেট শুধু একটি সারসংক্ষেপ। এটি আদালতের সম্পূর্ণ আদেশ নয়।"
                }
            },
            {
                id: "nextSteps",
                text: {
                    en: "Ask your lawyer if you need to prepare any document for the next date.",
                    bn: "পরবর্তী তারিখের জন্য কোনো নথি প্রস্তুত করতে হবে কি না, আপনার আইনজীবীকে জিজ্ঞাসা করুন।"
                }
            }
        ]
    },
    {
        id: "summary-h-24018-1",
        title: {
            en: "What happened at hearing 1",
            bn: "শুনানি ১-এ কী হয়েছে"
        },
        excerpt: {
            en: "The defendant entered appearance and the next date was fixed.",
            bn: "বিবাদী পক্ষ উপস্থিত হয়েছেন এবং পরবর্তী তারিখ নির্ধারণ করা হয়েছে।"
        },
        publishedOn: {
            en: "09 Oct 2024",
            bn: "০৯ অক্টোবর ২০২৪"
        },
        status: "approved",
        sections: [
            {
                id: "keyNotes",
                text: {
                    en: "The defendant came to court. The court fixed the next date for the case.",
                    bn: "বিবাদী পক্ষ আদালতে উপস্থিত হয়েছেন। আদালত মামলার পরবর্তী তারিখ নির্ধারণ করেছেন।"
                }
            },
            {
                id: "laws",
                text: {
                    en: "No legal question was decided at this hearing.",
                    bn: "এই শুনানিতে কোনো আইনি প্রশ্নের সিদ্ধান্ত হয়নি।"
                }
            },
            {
                id: "risks",
                text: {
                    en: "The case is still at an early stage, so the result is not known.",
                    bn: "মামলা এখনো প্রাথমিক পর্যায়ে, তাই ফলাফল জানা যায়নি।"
                }
            },
            {
                id: "rights",
                text: {
                    en: "You will be kept informed about the main steps in your case.",
                    bn: "আপনার মামলার প্রধান ধাপগুলো সম্পর্কে আপনাকে জানানো হবে।"
                }
            },
            {
                id: "notes",
                text: {
                    en: "This is a short update about the hearing, not legal advice.",
                    bn: "এটি শুনানি সম্পর্কে একটি সংক্ষিপ্ত আপডেট, আইনি পরামর্শ নয়।"
                }
            },
            {
                id: "nextSteps",
                text: {
                    en: "Contact your lawyer if your address or phone number changes.",
                    bn: "আপনার ঠিকানা বা ফোন নম্বর পরিবর্তন হলে আপনার আইনজীবীকে জানান।"
                }
            }
        ]
    },
    {
        id: "summary-internal-note",
        title: {
            en: "Internal preparation note",
            bn: "অভ্যন্তরীণ প্রস্তুতি নোট"
        },
        excerpt: {
            en: "Draft note for the legal team. Not approved for the client.",
            bn: "আইনি দলের জন্য খসড়া নোট। মক্কেলের জন্য অনুমোদিত নয়।"
        },
        publishedOn: {
            en: "16 Jan 2025",
            bn: "১৬ জানুয়ারি ২০২৫"
        },
        status: "draft"
    },
    {
        id: "summary-other-case",
        caseId: "LC-99999",
        title: {
            en: "Another client's summary",
            bn: "অন্য মক্কেলের সারসংক্ষেপ"
        },
        excerpt: {
            en: "This summary belongs to a different client and must not be shown.",
            bn: "এই সারসংক্ষেপটি অন্য মক্কেলের এবং এটি দেখানো যাবে না।"
        },
        publishedOn: {
            en: "01 Jan 2025",
            bn: "০১ জানুয়ারি ২০২৫"
        },
        status: "approved"
    }
];
}),
"[project]/src/lib/mock/hearingSummaries.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "hearingSummarySections",
    ()=>hearingSummarySections,
    "hearingSummaryVersions",
    ()=>hearingSummaryVersions
]);
const hearingSummaryVersions = {};
const hearingSummarySections = [
    {
        id: "keyNotes",
        claims: [
            {
                id: "key-1",
                type: "document",
                verification: "verified",
                text: {
                    en: "The filed papers identify the parties and the relief sought.",
                    bn: "দাখিলকৃত কাগজপত্রে পক্ষগণ ও প্রত্যাশিত প্রতিকার চিহ্নিত করা হয়েছে।"
                },
                source: {
                    en: "Page 1 of the case file",
                    bn: "মামলা ফাইলের পৃষ্ঠা ১"
                }
            },
            {
                id: "key-2",
                type: "lawyer",
                verification: "verified",
                text: {
                    en: "The hearing note records the appearance of the parties and the next step.",
                    bn: "শুনানির নোটে পক্ষগণের উপস্থিতি ও পরবর্তী ধাপ লিপিবদ্ধ আছে।"
                },
                source: {
                    en: "Hearing note",
                    bn: "শুনানির নোট"
                }
            }
        ]
    },
    {
        id: "laws",
        claims: [
            {
                id: "law-1",
                type: "document",
                verification: "verified",
                text: {
                    en: "The filed papers contain no verified citation to a statutory provision.",
                    bn: "দাখিলকৃত কাগজপত্রে কোনো যাচাইকৃত আইনি ধারার উল্লেখ নেই।"
                },
                source: {
                    en: "Page 4 of the filed papers",
                    bn: "দাখিলকৃত কাগজপত্রের পৃষ্ঠা ৪"
                }
            },
            {
                id: "law-2",
                type: "ai",
                verification: "unverified",
                text: {
                    en: "The applicable provision has not been verified; no legal conclusion is drawn.",
                    bn: "প্রযোজ্য ধারা যাচাই করা হয়নি; কোনো আইনি সিদ্ধান্তে পৌঁছানো হয়নি।"
                },
                source: {
                    en: "No verified legal source in the mock knowledge base",
                    bn: "মক জ্ঞানভাণ্ডারে কোনো যাচাইকৃত আইনি উৎস নেই"
                }
            }
        ]
    },
    {
        id: "risks",
        claims: [
            {
                id: "risk-1",
                type: "ai",
                verification: "unverified",
                text: {
                    en: "The record does not show whether the opposing party has challenged the filed instrument.",
                    bn: "বিরোধী পক্ষ দাখিলকৃত দলিল চ্যালেঞ্জ করেছে কি না, রেকর্ডে তা দেখানো হয় না।"
                },
                source: {
                    en: "Page 3 of the filed papers",
                    bn: "দাখিলকৃত কাগজপত্রের পৃষ্ঠা ৩"
                }
            },
            {
                id: "risk-2",
                type: "assumption",
                verification: "unverified",
                text: {
                    en: "The opposing party may raise an objection to the documents at the next date.",
                    bn: "পরবর্তী তারিখে বিরোধী পক্ষ নথিগুলোর বিরুদ্ধে আপত্তি তুলতে পারে।"
                },
                source: {
                    en: "No source — working assumption",
                    bn: "কোনো উৎস নেই — কর্মগত অনুমান"
                }
            }
        ]
    },
    {
        id: "rights",
        claims: [
            {
                id: "right-1",
                type: "lawyer",
                verification: "verified",
                text: {
                    en: "The client's right to be heard was recorded at the hearing.",
                    bn: "শুনানিতে মক্কেলের শোনার অধিকার লিপিবদ্ধ হয়েছে।"
                },
                source: {
                    en: "Hearing note",
                    bn: "শুনানির নোট"
                }
            },
            {
                id: "right-2",
                type: "ai",
                verification: "unverified",
                text: {
                    en: "The record does not establish whether any further procedural right was exercised.",
                    bn: "আর কোনো কার্যগত অধিকার প্রয়োগ করা হয়েছে কি না, রেকর্ডে তা প্রতিষ্ঠিত হয় না।"
                },
                source: {
                    en: "Hearing note",
                    bn: "শুনানির নোট"
                }
            }
        ]
    },
    {
        id: "notes",
        claims: [
            {
                id: "note-1",
                type: "document",
                verification: "verified",
                text: {
                    en: "The hearing note records the next step directed by the court.",
                    bn: "শুনানির নোটে আদালতের নির্দেশিত পরবর্তী ধাপ লিপিবদ্ধ আছে।"
                },
                source: {
                    en: "Hearing note",
                    bn: "শুনানির নোট"
                }
            },
            {
                id: "note-2",
                type: "assumption",
                verification: "unverified",
                text: {
                    en: "The note may be incomplete because it was entered after the hearing.",
                    bn: "শুনানি শেষে নোট লেখা হওয়ায় তা অসম্পূর্ণ হতে পারে।"
                },
                source: {
                    en: "No source — working assumption",
                    bn: "কোনো উৎস নেই — কর্মগত অনুমান"
                }
            }
        ]
    },
    {
        id: "nextSteps",
        claims: [
            {
                id: "next-1",
                type: "lawyer",
                verification: "verified",
                text: {
                    en: "Prepare the original documents for the next hearing date.",
                    bn: "পরবর্তী শুনানির তারিখের জন্য মূল নথি প্রস্তুত করুন।"
                },
                source: {
                    en: "Hearing note",
                    bn: "শুনানির নোট"
                }
            },
            {
                id: "next-2",
                type: "ai",
                verification: "unverified",
                text: {
                    en: "Confirm the next date from the court record before updating the client.",
                    bn: "মক্কেলকে জানানোর আগে আদালতের রেকর্ড থেকে পরবর্তী তারিখ নিশ্চিত করুন।"
                },
                source: {
                    en: "No verified court record",
                    bn: "কোনো যাচাইকৃত আদালত রেকর্ড নেই"
                }
            }
        ]
    }
];
}),
"[project]/src/lib/mock/lawyer.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "activities",
    ()=>activities,
    "caseTypes",
    ()=>caseTypes,
    "clients",
    ()=>clients,
    "courts",
    ()=>courts,
    "documents",
    ()=>documents,
    "hearings",
    ()=>hearings,
    "lawyerProfile",
    ()=>lawyerProfile,
    "matterStages",
    ()=>matterStages,
    "matters",
    ()=>matters
]);
const matterStages = [
    {
        id: "filed",
        label: {
            en: "Case filed",
            bn: "মামলা দায়ের"
        }
    },
    {
        id: "notice",
        label: {
            en: "Notice served",
            bn: "নোটিশ জারি"
        }
    },
    {
        id: "evidence",
        label: {
            en: "Evidence",
            bn: "সাক্ষ্য"
        }
    },
    {
        id: "arguments",
        label: {
            en: "Arguments",
            bn: "যুক্তিতর্ক"
        }
    },
    {
        id: "decision",
        label: {
            en: "Decision",
            bn: "রায়"
        }
    }
];
const lawyerProfile = {
    firstName: {
        en: "Farhana",
        bn: "ফারহানা"
    },
    name: {
        en: "Farhana Ahmed",
        bn: "ফারহানা আহমেদ"
    },
    email: "farhana@rahmanlaw.bd",
    firm: {
        en: "Rahman & Associates",
        bn: "রহমান অ্যান্ড অ্যাসোসিয়েটস"
    },
    location: {
        en: "Dhaka, Bangladesh",
        bn: "ঢাকা, বাংলাদেশ"
    }
};
const matters = [
    {
        id: "LC-24018",
        title: {
            en: "Rahman vs. Karim",
            bn: "রহমান বনাম করিম"
        },
        clientId: "CL-7842-BD",
        clientName: {
            en: "Fahim Rahman",
            bn: "ফাহিম রহমান"
        },
        court: {
            en: "Dhaka District Court",
            bn: "ঢাকা জেলা আদালত"
        },
        caseType: {
            en: "Property dispute",
            bn: "সম্পত্তি বিরোধ"
        },
        hearingNumber: 3,
        status: "active",
        nextHearing: {
            day: 17,
            month: {
                en: "JAN",
                bn: "জানু"
            },
            time: {
                en: "10:30 AM",
                bn: "সকাল ১০:৩০"
            }
        },
        stages: [
            {
                ...matterStages[0],
                date: {
                    en: "12 Sep",
                    bn: "১২ সেপ্টেম্বর"
                }
            },
            {
                ...matterStages[1],
                date: {
                    en: "28 Sep",
                    bn: "২৮ সেপ্টেম্বর"
                }
            },
            matterStages[2],
            matterStages[3],
            matterStages[4]
        ],
        currentStageId: "evidence"
    },
    {
        id: "LC-24012",
        title: {
            en: "Ahmed Property Matter",
            bn: "আহমেদ সম্পত্তি বিষয়ক"
        },
        clientId: "CL-7851-BD",
        clientName: {
            en: "Nusrat Ahmed",
            bn: "নুসরাত আহমেদ"
        },
        court: {
            en: "High Court Division",
            bn: "হাইকোর্ট বিভাগ"
        },
        caseType: {
            en: "Property dispute",
            bn: "সম্পত্তি বিরোধ"
        },
        hearingNumber: 2,
        status: "active",
        nextHearing: {
            day: 19,
            month: {
                en: "JAN",
                bn: "জানু"
            },
            time: {
                en: "12:00 PM",
                bn: "দুপুর ১২:০০"
            }
        },
        stages: [
            {
                ...matterStages[0],
                date: {
                    en: "02 Dec",
                    bn: "২ ডিসেম্বর"
                }
            },
            {
                ...matterStages[1],
                date: {
                    en: "20 Dec",
                    bn: "২০ ডিসেম্বর"
                }
            },
            matterStages[2],
            matterStages[3],
            matterStages[4]
        ],
        currentStageId: "evidence"
    },
    {
        id: "LC-23997",
        title: {
            en: "Khan & Co. Agreement",
            bn: "খান অ্যান্ড কোং চুক্তি"
        },
        clientId: "CL-7863-BD",
        clientName: {
            en: "Rafiq Khan",
            bn: "রফিক খান"
        },
        court: {
            en: "Arbitration Tribunal",
            bn: "সালিশি ট্রাইব্যুনাল"
        },
        caseType: {
            en: "Contract",
            bn: "চুক্তি"
        },
        hearingNumber: 5,
        status: "active",
        nextHearing: {
            day: 21,
            month: {
                en: "JAN",
                bn: "জানু"
            },
            time: {
                en: "11:15 AM",
                bn: "সকাল ১১:১৫"
            }
        },
        stages: [
            {
                ...matterStages[0],
                date: {
                    en: "10 Aug",
                    bn: "১০ আগস্ট"
                }
            },
            {
                ...matterStages[1],
                date: {
                    en: "22 Aug",
                    bn: "২২ আগস্ট"
                }
            },
            {
                ...matterStages[2],
                date: {
                    en: "15 Oct",
                    bn: "১৫ অক্টোবর"
                }
            },
            matterStages[3],
            matterStages[4]
        ],
        currentStageId: "arguments"
    },
    {
        id: "LC-23986",
        title: {
            en: "Sultana Family Matter",
            bn: "সুলতানা পারিবারিক বিষয়"
        },
        clientId: "CL-7870-BD",
        clientName: {
            en: "Samira Sultana",
            bn: "সামিরা সুলতানা"
        },
        court: {
            en: "Family Court, Dhaka",
            bn: "পারিবারিক আদালত, ঢাকা"
        },
        caseType: {
            en: "Family",
            bn: "পারিবারিক"
        },
        hearingNumber: 4,
        status: "closed",
        stages: [
            {
                ...matterStages[0],
                date: {
                    en: "05 Mar",
                    bn: "৫ মার্চ"
                }
            },
            {
                ...matterStages[1],
                date: {
                    en: "18 Mar",
                    bn: "১৮ মার্চ"
                }
            },
            {
                ...matterStages[2],
                date: {
                    en: "20 Jun",
                    bn: "২০ জুন"
                }
            },
            {
                ...matterStages[3],
                date: {
                    en: "02 Sep",
                    bn: "২ সেপ্টেম্বর"
                }
            },
            {
                ...matterStages[4],
                date: {
                    en: "14 Nov 2024",
                    bn: "১৪ নভেম্বর ২০২৪"
                }
            }
        ],
        currentStageId: "decision"
    }
];
const dhakaDistrict = {
    en: "Dhaka District Court",
    bn: "ঢাকা জেলা আদালত"
};
const highCourt = {
    en: "High Court Division",
    bn: "হাইকোর্ট বিভাগ"
};
const arbitration = {
    en: "Arbitration Tribunal",
    bn: "সালিশি ট্রাইব্যুনাল"
};
const familyCourt = {
    en: "Family Court, Dhaka",
    bn: "পারিবারিক আদালত, ঢাকা"
};
const hearings = {
    "LC-24018": [
        {
            id: "h-24018-1",
            number: 1,
            date: "2024-10-08",
            court: dhakaDistrict,
            summaryStatus: "approved",
            notes: [
                {
                    id: "h-24018-1-n1",
                    text: "Defendant entered appearance. Next date fixed for framing of issues."
                }
            ]
        },
        {
            id: "h-24018-2",
            number: 2,
            date: "2024-11-21",
            court: dhakaDistrict,
            summaryStatus: "draft_ready",
            notes: [
                {
                    id: "h-24018-2-n1",
                    text: "Court framed issues for trial."
                },
                {
                    id: "h-24018-2-n2",
                    text: "Four issues framed; two deferred to the next date."
                }
            ]
        },
        {
            id: "h-24018-3",
            number: 3,
            date: "2025-01-17",
            court: dhakaDistrict,
            summaryStatus: "draft_ready",
            notes: [
                {
                    id: "h-24018-3-n1",
                    text: "Plaintiff witness examination. Bring the original deed."
                }
            ]
        }
    ],
    "LC-24012": [
        {
            id: "h-24012-1",
            number: 1,
            date: "2024-12-02",
            court: highCourt,
            summaryStatus: "draft_ready",
            notes: [
                {
                    id: "h-24012-1-n1",
                    text: "Case transferred to the High Court Division. Parties notified."
                }
            ]
        },
        {
            id: "h-24012-2",
            number: 2,
            date: "2024-12-20",
            court: highCourt,
            summaryStatus: "draft_ready",
            notes: [
                {
                    id: "h-24012-2-n1",
                    text: "Interim order hearing scheduled. Certified copy of the deed filed."
                }
            ]
        }
    ],
    "LC-23997": [
        {
            id: "h-23997-1",
            number: 1,
            date: "2024-08-10",
            court: arbitration,
            summaryStatus: "processing",
            notes: [
                {
                    id: "h-23997-1-n1",
                    text: "First sitting. Tribunal constituted and parties identified."
                }
            ]
        },
        {
            id: "h-23997-2",
            number: 2,
            date: "2024-08-22",
            court: arbitration,
            summaryStatus: "processing",
            notes: [
                {
                    id: "h-23997-2-n1",
                    text: "Procedural timetable agreed. Claimant to file documents."
                }
            ]
        },
        {
            id: "h-23997-3",
            number: 3,
            date: "2024-10-15",
            court: arbitration,
            summaryStatus: "processing",
            notes: [
                {
                    id: "h-23997-3-n1",
                    text: "Claimant's documents filed. Respondent sought time to reply."
                }
            ]
        },
        {
            id: "h-23997-4",
            number: 4,
            date: "2024-12-05",
            court: arbitration,
            summaryStatus: "processing",
            notes: [
                {
                    id: "h-23997-4-n1",
                    text: "Reply filed. Tribunal directed parties to exchange witness lists."
                }
            ]
        },
        {
            id: "h-23997-5",
            number: 5,
            date: "2025-01-21",
            court: arbitration,
            summaryStatus: "processing",
            notes: [
                {
                    id: "h-23997-5-n1",
                    text: "Witness lists due. Hearing on the preliminary objection."
                }
            ]
        }
    ],
    "LC-23986": [
        {
            id: "h-23986-1",
            number: 1,
            date: "2024-03-05",
            court: familyCourt,
            summaryStatus: "approved",
            notes: [
                {
                    id: "h-23986-1-n1",
                    text: "First appearance. Parties referred to mediation."
                }
            ]
        },
        {
            id: "h-23986-2",
            number: 2,
            date: "2024-03-18",
            court: familyCourt,
            summaryStatus: "approved",
            notes: [
                {
                    id: "h-23986-2-n1",
                    text: "Mediation did not settle the matter. Evidence directions given."
                }
            ]
        },
        {
            id: "h-23986-3",
            number: 3,
            date: "2024-06-20",
            court: familyCourt,
            summaryStatus: "approved",
            notes: [
                {
                    id: "h-23986-3-n1",
                    text: "Evidence recorded. Final arguments scheduled."
                }
            ]
        },
        {
            id: "h-23986-4",
            number: 4,
            date: "2024-09-02",
            court: familyCourt,
            summaryStatus: "approved",
            notes: [
                {
                    id: "h-23986-4-n1",
                    text: "Final arguments heard. Judgment reserved."
                }
            ]
        }
    ]
};
const documents = {
    "LC-24018": [
        {
            id: "doc-24018-1",
            hearingId: "h-24018-1",
            name: "Notice_of_Suit.pdf",
            size: 248000,
            mimeType: "application/pdf",
            status: "ready"
        },
        {
            id: "doc-24018-2",
            hearingId: "h-24018-2",
            name: "Written_Statement.pdf",
            size: 512000,
            mimeType: "application/pdf",
            status: "ready"
        },
        {
            id: "doc-24018-3",
            hearingId: "h-24018-2",
            name: "Witness_List.pdf",
            size: 96000,
            mimeType: "application/pdf",
            status: "failed"
        },
        {
            id: "doc-24018-4",
            hearingId: "h-24018-3",
            name: "Deed_of_Sale.pdf",
            size: 3400000,
            mimeType: "application/pdf",
            status: "ready"
        },
        {
            id: "doc-24018-5",
            hearingId: "h-24018-3",
            name: "Site_Photo_01.jpg",
            size: 2100000,
            mimeType: "image/jpeg",
            status: "ready"
        },
        {
            id: "doc-24018-6",
            hearingId: "h-24018-3",
            name: "Plaintiff_Affidavit.pdf",
            size: 1250000,
            mimeType: "application/pdf",
            status: "processing"
        }
    ],
    "LC-24012": [
        {
            id: "doc-24012-1",
            hearingId: "h-24012-1",
            name: "Transfer_Order.pdf",
            size: 320000,
            mimeType: "application/pdf",
            status: "ready"
        },
        {
            id: "doc-24012-2",
            hearingId: "h-24012-2",
            name: "Interim_Order_Copy.pdf",
            size: 410000,
            mimeType: "application/pdf",
            status: "ready"
        }
    ],
    "LC-23997": [
        {
            id: "doc-23997-1",
            hearingId: "h-23997-1",
            name: "Arbitration_Agreement.pdf",
            size: 880000,
            mimeType: "application/pdf",
            status: "ready"
        },
        {
            id: "doc-23997-2",
            hearingId: "h-23997-3",
            name: "Claimant_Documents.pdf",
            size: 2600000,
            mimeType: "application/pdf",
            status: "ready"
        },
        {
            id: "doc-23997-3",
            hearingId: "h-23997-5",
            name: "Witness_List.pdf",
            size: 140000,
            mimeType: "application/pdf",
            status: "processing"
        }
    ],
    "LC-23986": [
        {
            id: "doc-23986-1",
            hearingId: "h-23986-4",
            name: "Judgment_Copy.pdf",
            size: 1900000,
            mimeType: "application/pdf",
            status: "ready"
        }
    ]
};
const clients = [
    {
        id: "CL-7842-BD",
        name: {
            en: "Fahim Rahman",
            bn: "ফাহিম রহমান"
        },
        phone: "+880 1711-234567",
        email: "fahim.rahman@example.com"
    },
    {
        id: "CL-7851-BD",
        name: {
            en: "Nusrat Ahmed",
            bn: "নুসরাত আহমেদ"
        },
        phone: "+880 1812-345678",
        email: "nusrat.ahmed@example.com"
    },
    {
        id: "CL-7863-BD",
        name: {
            en: "Rafiq Khan",
            bn: "রফিক খান"
        },
        phone: "+880 1913-456789",
        email: "rafiq.khan@example.com"
    },
    {
        id: "CL-7870-BD",
        name: {
            en: "Samira Sultana",
            bn: "সামিরা সুলতানা"
        },
        phone: "+880 1614-567890",
        email: "samira.sultana@example.com"
    }
];
const activities = [
    {
        id: "activity-document",
        icon: "document",
        title: {
            en: "Document added",
            bn: "নথি যোগ হয়েছে"
        },
        detail: {
            en: "Witness_Statement.pdf",
            bn: "সাক্ষীর_বিবৃতি.pdf"
        },
        time: {
            en: "18 min ago",
            bn: "১৮ মিনিট আগে"
        }
    },
    {
        id: "activity-hearing",
        icon: "calendar",
        title: {
            en: "Hearing rescheduled",
            bn: "শুনানির সময় পরিবর্তন"
        },
        detail: {
            en: "Ahmed Property Matter",
            bn: "আহমেদ সম্পত্তি বিষয়ক"
        },
        time: {
            en: "2 hours ago",
            bn: "২ ঘণ্টা আগে"
        }
    },
    {
        id: "activity-client",
        icon: "clients",
        title: {
            en: "New client created",
            bn: "নতুন মক্কেল তৈরি"
        },
        detail: {
            en: "Samira Sultana",
            bn: "সামিরা সুলতানা"
        },
        time: {
            en: "Yesterday",
            bn: "গতকাল"
        }
    }
];
const courts = [
    {
        en: "Dhaka District Court",
        bn: "ঢাকা জেলা আদালত"
    },
    {
        en: "High Court Division",
        bn: "হাইকোর্ট বিভাগ"
    },
    {
        en: "Arbitration Tribunal",
        bn: "সালিশি ট্রাইব্যুনাল"
    },
    {
        en: "Family Court, Dhaka",
        bn: "পারিবারিক আদালত, ঢাকা"
    }
];
const caseTypes = [
    {
        en: "Property dispute",
        bn: "সম্পত্তি বিরোধ"
    },
    {
        en: "Contract",
        bn: "চুক্তি"
    },
    {
        en: "Family",
        bn: "পারিবারিক"
    },
    {
        en: "Criminal",
        bn: "ফৌজদারি"
    }
];
}),
"[project]/src/lib/session.ts [app-rsc] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "clearSession",
    ()=>clearSession,
    "getSession",
    ()=>getSession,
    "isMockAuthEnabled",
    ()=>isMockAuthEnabled,
    "setMockSession",
    ()=>setMockSession
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$headers$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/node_modules/next/headers.js [app-rsc] (ecmascript)");
;
;
const SESSION_COOKIE = "lc_session";
const MOCK_PREFIX = "mock.";
const SESSION_MAX_AGE = 60 * 60 * 8;
function cookieOptions() {
    return {
        httpOnly: true,
        sameSite: "lax",
        secure: ("TURBOPACK compile-time value", "development") === "production",
        path: "/",
        maxAge: SESSION_MAX_AGE
    };
}
function isMockAuthEnabled() {
    return ("TURBOPACK compile-time value", "development") !== "production" && process.env.MOCK_AUTH === "true";
}
async function getSession() {
    if (!isMockAuthEnabled()) return null;
    const value = (await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$headers$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["cookies"])()).get(SESSION_COOKIE)?.value;
    if (!value?.startsWith(MOCK_PREFIX)) return null;
    const role = value.slice(MOCK_PREFIX.length);
    return role === "lawyer" || role === "client" ? {
        role
    } : null;
}
async function setMockSession(role) {
    if (!isMockAuthEnabled()) return false;
    const store = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$headers$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["cookies"])();
    store.set(SESSION_COOKIE, `${MOCK_PREFIX}${role}`, cookieOptions());
    return true;
}
async function clearSession() {
    const store = await (0, __TURBOPACK__imported__module__$5b$project$5d2f$node_modules$2f$next$2f$headers$2e$js__$5b$app$2d$rsc$5d$__$28$ecmascript$29$__["cookies"])();
    store.set(SESSION_COOKIE, "", {
        ...cookieOptions(),
        maxAge: 0
    });
}
}),
];

//# sourceMappingURL=_1r59pkn3-tqlo._.js.map