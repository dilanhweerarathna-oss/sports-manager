from __future__ import annotations
from models.sport import Sport
from models.coach import Coach
from models.mic import MIC
from repositories.sport_repository import SportRepository
from repositories.coach_repository import CoachRepository
from repositories.mic_repository import MICRepository
from services.log_service import LogService
from utils.exceptions import ValidationError
from utils.logger import get_logger

logger = get_logger("sport_service")


class SportService:
    def __init__(self) -> None:
        self._sports  = SportRepository()
        self._coaches = CoachRepository()
        self._mics    = MICRepository()
        self._log     = LogService()

    # ── Sports CRUD ───────────────────────────────────────────────────────────

    def get_all(self) -> list[Sport]:
        return self._sports.get_all()

    def get_active(self) -> list[Sport]:
        return self._sports.get_active()

    def get_by_id(self, sport_id: int) -> Sport:
        s = self._sports.get_by_id(sport_id)
        if not s:
            raise ValueError(f"Sport {sport_id} not found")
        return s

    def create(self, data: dict) -> Sport:
        self._validate_sport(data)
        sport = Sport(
            id=None,
            sport_name=data["sport_name"].strip(),
            monthly_fee=float(data.get("monthly_fee", 0)),
            registration_fee=float(data.get("registration_fee", 0)),
            active_status=int(data.get("active_status", 1)),
            notes=data.get("notes") or None,
        )
        saved = self._sports.insert(sport)
        self._log.create("sports", saved.id, f"Added sport: {saved.sport_name}")
        return saved

    def update(self, sport_id: int, data: dict) -> Sport:
        self._validate_sport(data, exclude_id=sport_id)
        s = self.get_by_id(sport_id)
        s.sport_name       = data.get("sport_name", s.sport_name).strip()
        s.monthly_fee      = float(data.get("monthly_fee", s.monthly_fee))
        s.registration_fee = float(data.get("registration_fee", s.registration_fee))
        s.active_status    = int(data.get("active_status", s.active_status))
        s.notes            = data.get("notes") or s.notes
        saved = self._sports.update(s)
        self._log.update("sports", saved.id, f"Updated sport: {saved.sport_name}")
        return saved

    def delete(self, sport_id: int) -> None:
        s = self.get_by_id(sport_id)
        self._sports.delete(sport_id)
        self._log.delete("sports", sport_id, f"Deleted sport: {s.sport_name}")

    def toggle_active(self, sport_id: int) -> Sport:
        s = self.get_by_id(sport_id)
        s.active_status = 0 if s.active_status else 1
        saved = self._sports.update(s)
        self._log.update("sports", saved.id,
                         f"Sport {saved.sport_name} active -> {saved.active_status}")
        return saved

    # ── Coach management ──────────────────────────────────────────────────────

    def get_all_coaches(self) -> list[Coach]:
        return self._coaches.get_all()

    def get_coaches(self, sport_id: int) -> list[Coach]:
        return self._sports.get_coaches(sport_id)

    def create_coach(self, data: dict) -> Coach:
        if not data.get("full_name", "").strip():
            raise ValidationError("full_name", "Full name is required")
        c = Coach(
            id=None,
            full_name=data["full_name"].strip(),
            contact_no=data.get("contact_no") or None,
            email=data.get("email") or None,
            address=data.get("address") or None,
            active_status=int(data.get("active_status", 1)),
            notes=data.get("notes") or None,
        )
        saved = self._coaches.insert(c)
        self._log.create("coaches", saved.id, f"Added coach: {saved.full_name}")
        return saved

    def update_coach(self, coach_id: int, data: dict) -> Coach:
        if not data.get("full_name", "").strip():
            raise ValidationError("full_name", "Full name is required")
        c = self._coaches.get_by_id(coach_id)
        if not c:
            raise ValueError(f"Coach {coach_id} not found")
        c.full_name    = data["full_name"].strip()
        c.contact_no   = data.get("contact_no") or c.contact_no
        c.email        = data.get("email") or c.email
        c.address      = data.get("address") or c.address
        c.active_status= int(data.get("active_status", c.active_status))
        c.notes        = data.get("notes") or c.notes
        saved = self._coaches.update(c)
        self._log.update("coaches", saved.id, f"Updated coach: {saved.full_name}")
        return saved

    def delete_coach(self, coach_id: int) -> None:
        c = self._coaches.get_by_id(coach_id)
        if c:
            self._coaches.delete(coach_id)
            self._log.delete("coaches", coach_id, f"Deleted coach: {c.full_name}")

    def assign_coach(self, sport_id: int, coach_id: int) -> None:
        self._sports.assign_coach(sport_id, coach_id)

    def remove_coach(self, sport_id: int, coach_id: int) -> None:
        self._sports.remove_coach(sport_id, coach_id)

    # ── MIC management ────────────────────────────────────────────────────────

    def get_all_mics(self) -> list[MIC]:
        return self._mics.get_all()

    def get_mics(self, sport_id: int) -> list[MIC]:
        return self._sports.get_mics(sport_id)

    def create_mic(self, data: dict) -> MIC:
        if not data.get("full_name", "").strip():
            raise ValidationError("full_name", "Full name is required")
        m = MIC(
            id=None,
            full_name=data["full_name"].strip(),
            contact_no=data.get("contact_no") or None,
            email=data.get("email") or None,
            active_status=int(data.get("active_status", 1)),
            notes=data.get("notes") or None,
        )
        saved = self._mics.insert(m)
        self._log.create("mics", saved.id, f"Added MIC: {saved.full_name}")
        return saved

    def update_mic(self, mic_id: int, data: dict) -> MIC:
        if not data.get("full_name", "").strip():
            raise ValidationError("full_name", "Full name is required")
        m = self._mics.get_by_id(mic_id)
        if not m:
            raise ValueError(f"MIC {mic_id} not found")
        m.full_name    = data["full_name"].strip()
        m.contact_no   = data.get("contact_no") or m.contact_no
        m.email        = data.get("email") or m.email
        m.active_status= int(data.get("active_status", m.active_status))
        m.notes        = data.get("notes") or m.notes
        saved = self._mics.update(m)
        self._log.update("mics", saved.id, f"Updated MIC: {saved.full_name}")
        return saved

    def delete_mic(self, mic_id: int) -> None:
        m = self._mics.get_by_id(mic_id)
        if m:
            self._mics.delete(mic_id)
            self._log.delete("mics", mic_id, f"Deleted MIC: {m.full_name}")

    def assign_mic(self, sport_id: int, mic_id: int) -> None:
        self._sports.assign_mic(sport_id, mic_id)

    def remove_mic(self, sport_id: int, mic_id: int) -> None:
        self._sports.remove_mic(sport_id, mic_id)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _validate_sport(self, data: dict, exclude_id: int | None = None) -> None:
        name = data.get("sport_name", "").strip()
        if not name:
            raise ValidationError("sport_name", "Sport name is required")
        existing = [s for s in self._sports.get_all() if s.sport_name.lower() == name.lower()]
        if existing and existing[0].id != exclude_id:
            raise ValidationError("sport_name", f"Sport '{name}' already exists")
