###############################################################################
# 운영용 사설 통합: 내부 NLB + VPC Link  (use_vpc_link=true 일 때만 생성)
#
#   API Gateway ──VPC Link──▶ 내부 NLB(:listener_port) ──forward──▶ EC2 FastAPI(:8000, 비공개)
#
# 활성화 시 EC2 8000을 공개하지 않아도 됨(SG는 NLB만 허용). false면 전부 미생성(공개 PoC 경로).
###############################################################################

resource "aws_lb" "nlb" {
  count              = var.use_vpc_link ? 1 : 0
  name               = "${var.name_prefix}-nlb"
  internal           = true
  load_balancer_type = "network"
  subnets            = var.nlb_subnet_ids
}

resource "aws_lb_target_group" "fastapi" {
  count       = var.use_vpc_link ? 1 : 0
  name        = "${var.name_prefix}-tg"
  port        = var.backend_port
  protocol    = "TCP"
  vpc_id      = var.vpc_id
  target_type = "instance"

  health_check {
    protocol = "HTTP"
    path     = "/health"
    port     = "traffic-port"
  }
}

resource "aws_lb_target_group_attachment" "fastapi" {
  count            = var.use_vpc_link ? 1 : 0
  target_group_arn = aws_lb_target_group.fastapi[0].arn
  target_id        = var.backend_instance_id
  port             = var.backend_port
}

resource "aws_lb_listener" "fastapi" {
  count             = var.use_vpc_link ? 1 : 0
  load_balancer_arn = aws_lb.nlb[0].arn
  port              = var.nlb_listener_port
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.fastapi[0].arn
  }
}

resource "aws_api_gateway_vpc_link" "this" {
  count       = var.use_vpc_link ? 1 : 0
  name        = "${var.name_prefix}-vpclink"
  description = "REST API → 내부 NLB 사설 통합"
  target_arns = [aws_lb.nlb[0].arn]
}
