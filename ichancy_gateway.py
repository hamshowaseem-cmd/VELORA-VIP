"""بوابة ربط iChancy - طبقة تمهيدية آمنة.

لا تنفذ هذه الوحدة أي تحويلات مالية. يجب استكمالها فقط وفق وثائق API
رسمية من iChancy، ثم اختبارها في بيئة تجريبية قبل تفعيلها.
"""
import os


class IchancyNotConfigured(RuntimeError):
    """تظهر عندما لا يكون الربط الرسمي مهيأً."""


def auto_deposit_enabled() -> bool:
    """التعبئة الآلية متوقفة افتراضياً حتى توافر API رسمي ومختبر."""
    return os.getenv("ICHANCY_AUTO_DEPOSIT_ENABLED", "false").strip().lower() == "true"


def verify_external_payment(payment_reference: str):
    """يتحقق من الدفع عبر API رسمي بعد تنفيذ الربط؛ لا يقبل صور الإيصالات وحدها."""
    if not auto_deposit_enabled():
        raise IchancyNotConfigured(
            "التعبئة الآلية متوقفة: يلزم ربط API رسمي من iChancy."
        )
    raise IchancyNotConfigured(
        "لم تتم برمجة التحقق بعد؛ يلزم تحديد نقطة API الرسمية وحقولها."
    )


def credit_player(player_identifier: str, amount: str, currency: str, idempotency_key: str):
    """ينفذ إيداع اللاعب عبر API رسمي بعد التحقق؛ لا ينفذ أي تحويل حالياً."""
    if not auto_deposit_enabled():
        raise IchancyNotConfigured(
            "تنفيذ الإيداع متوقف: يلزم ربط API رسمي من iChancy."
        )
    raise IchancyNotConfigured(
        "لم تتم برمجة الإيداع بعد؛ يلزم تحديد نقطة API الرسمية وحقولها."
    )


def submit_withdrawal_for_owner_approval(request_id: int) -> str:
    """يُبقي السحب بانتظار موافقة المالك؛ لا ينفذ سحباً تلقائياً."""
    return "pending_owner_approval"
