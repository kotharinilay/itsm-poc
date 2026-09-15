import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DesignSystem } from './design-system';

describe('DesignSystem', () => {
  let component: DesignSystem;
  let fixture: ComponentFixture<DesignSystem>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DesignSystem],
    }).compileComponents();

    fixture = TestBed.createComponent(DesignSystem);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
