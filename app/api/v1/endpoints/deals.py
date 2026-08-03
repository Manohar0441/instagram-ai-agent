from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_deal_service
from app.models.user import User
from app.schemas.deals import (
    DealCreate,
    DealResponse,
    DealStatus,
    DealUpdate,
    EarningsPeriod,
    EarningsSummaryResponse,
    PaymentStatus,
)
from app.services.deals_service import DealHasNoDatesError, DealNotFoundError, DealService

router = APIRouter(prefix="/deals", tags=["Deals"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DealServiceDependency = Annotated[DealService, Depends(get_deal_service)]


def _not_found(exc: DealNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "",
    response_model=DealResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log a new deal",
    description="Log a new brand collaboration or content-creation gig for the current user.",
    operation_id="createDeal",
)
def create_deal(
    payload: DealCreate,
    current_user: CurrentUser,
    deal_service: DealServiceDependency,
) -> DealResponse:
    """Create a new deal for the current user."""
    deal = deal_service.create_deal(current_user.id, payload)
    return DealResponse.model_validate(deal)


@router.get(
    "",
    response_model=list[DealResponse],
    status_code=status.HTTP_200_OK,
    summary="List deals",
    description="List the current user's deals, most recently shot first, optionally filtered.",
    operation_id="listDeals",
)
def list_deals(
    current_user: CurrentUser,
    deal_service: DealServiceDependency,
    deal_status: DealStatus | None = Query(default=None),
    payment_status: PaymentStatus | None = Query(default=None),
    shoot_from: date | None = Query(default=None),
    shoot_to: date | None = Query(default=None),
) -> list[DealResponse]:
    """Return the current user's deals, optionally filtered by status or shoot date range."""
    deals = deal_service.list_deals(
        current_user.id,
        deal_status=deal_status,
        payment_status=payment_status,
        shoot_from=shoot_from,
        shoot_to=shoot_to,
    )
    return [DealResponse.model_validate(deal) for deal in deals]


# Declared before /{deal_id} - otherwise Starlette would try to parse
# "earnings-summary" as deal_id: int and return 422 instead of matching here.
@router.get(
    "/earnings-summary",
    response_model=EarningsSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get earnings summary",
    description="Summarize paid and pending totals per currency, bucketed weekly, monthly, or yearly.",
    operation_id="getDealsEarningsSummary",
)
def get_earnings_summary(
    current_user: CurrentUser,
    deal_service: DealServiceDependency,
    period: EarningsPeriod = Query(default="monthly"),
) -> EarningsSummaryResponse:
    """Return the current user's earnings summary for the given period."""
    return deal_service.get_earnings_summary(current_user.id, period)


@router.get(
    "/{deal_id}",
    response_model=DealResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a deal",
    description="Return a single deal owned by the current user.",
    operation_id="getDeal",
    responses={status.HTTP_404_NOT_FOUND: {"description": "No deal with this ID was found."}},
)
def get_deal(
    deal_id: int,
    current_user: CurrentUser,
    deal_service: DealServiceDependency,
) -> DealResponse:
    """Return a single deal owned by the current user."""
    try:
        return DealResponse.model_validate(deal_service.get_deal(current_user.id, deal_id))
    except DealNotFoundError as exc:
        raise _not_found(exc) from exc


@router.put(
    "/{deal_id}",
    response_model=DealResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a deal",
    description="Replace every field of a deal owned by the current user.",
    operation_id="updateDeal",
    responses={status.HTTP_404_NOT_FOUND: {"description": "No deal with this ID was found."}},
)
def update_deal(
    deal_id: int,
    payload: DealUpdate,
    current_user: CurrentUser,
    deal_service: DealServiceDependency,
) -> DealResponse:
    """Replace every field of a deal owned by the current user."""
    try:
        return DealResponse.model_validate(deal_service.update_deal(current_user.id, deal_id, payload))
    except DealNotFoundError as exc:
        raise _not_found(exc) from exc


@router.delete(
    "/{deal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a deal",
    description="Delete a deal owned by the current user.",
    operation_id="deleteDeal",
    responses={status.HTTP_404_NOT_FOUND: {"description": "No deal with this ID was found."}},
)
def delete_deal(
    deal_id: int,
    current_user: CurrentUser,
    deal_service: DealServiceDependency,
) -> None:
    """Delete a deal owned by the current user."""
    try:
        deal_service.delete_deal(current_user.id, deal_id)
    except DealNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get(
    "/{deal_id}/ics",
    status_code=status.HTTP_200_OK,
    summary="Download a deal's calendar file",
    description=(
        "Download a .ics calendar file containing the deal's shoot date and/or "
        "payment due date, each with a reminder, for import into any calendar app."
    ),
    operation_id="downloadDealIcs",
    responses={
        status.HTTP_200_OK: {"description": "Calendar file generated successfully."},
        status.HTTP_404_NOT_FOUND: {"description": "No deal with this ID was found."},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "The deal has neither a shoot date nor a payment due date."
        },
    },
)
def download_deal_ics(
    deal_id: int,
    current_user: CurrentUser,
    deal_service: DealServiceDependency,
) -> Response:
    """Return a downloadable .ics file for the deal's shoot and/or payment due date."""
    try:
        ics_text = deal_service.get_ics(current_user.id, deal_id)
    except DealNotFoundError as exc:
        raise _not_found(exc) from exc
    except DealHasNoDatesError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return Response(
        content=ics_text,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="deal-{deal_id}.ics"'},
    )
